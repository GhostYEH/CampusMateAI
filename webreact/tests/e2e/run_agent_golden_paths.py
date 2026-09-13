"""Agent 三条黄金路径 E2E 入口: 启动后端(fake provider)+前端 dev,执行 Playwright 检查后回收。

用法:
    cd webreact && python tests/e2e/run_agent_golden_paths.py
    cd webreact && python tests/e2e/run_agent_golden_paths.py --final-review-only
    cd webreact && python tests/e2e/run_agent_golden_paths.py --notice-only
    cd webreact && python tests/e2e/run_agent_golden_paths.py --course-research-only

行为:
- 后端用隔离 SQLite 文件(e2e_agent_test.db),启动前删除,确保不依赖残留数据。
- 后端以 APP_ENV=test + AGENT_ALLOW_MOCK_PROVIDERS=true 启动,fake provider 自动注入。
- 前端 dev 用动态端口,代理到后端端口。
- 依次执行三条黄金路径脚本,任一失败即整体失败。
- 成功或失败都回收后端与前端进程,不残留。
"""
import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEBREACT = HERE.parent.parent
REPO_ROOT = WEBREACT.parent
BACKEND = REPO_ROOT / "backend"
BASE_BACKEND_PORT = int(os.environ.get("AGENT_E2E_BACKEND_PORT", "8765"))
BASE_FRONTEND_PORT = int(os.environ.get("AGENT_E2E_FRONTEND_PORT", "5184"))
MAX_TRIES = 10
START_TIMEOUT_SECONDS = 90

SCRIPTS = {
    "final-review": HERE / "final_review_golden_path.py",
    "notice": HERE / "notice_workflow_golden_path.py",
    "course-research": HERE / "course_research_golden_path.py",
}

DEMO_USERNAME = "student_demo"
DEMO_PASSWORD = "Demo123456"


def find_free_port(start):
    for port in range(start, start + MAX_TRIES):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", 0))
        except OSError as exc:
            raise RuntimeError(f"在 {start} 起连续 {MAX_TRIES} 个端口均被占用: {exc}")
        return sock.getsockname()[1]


def wait_for_http(url, timeout=START_TIMEOUT_SECONDS):
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    return
                last_error = f"非 200 状态: {response.status}"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(1)
    raise RuntimeError(f"{url} 在 {timeout}s 内未就绪,最后错误: {last_error}")


def port_is_free(port):
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def wait_for_port_release(port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_is_free(port):
            return True
        time.sleep(0.2)
    return False


def stop_process_tree(proc):
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            proc.kill()
        else:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        proc.wait(timeout=5)


def start_backend(port):
    """以 test + fake provider 模式启动后端。"""
    db_path = BACKEND / "data" / "e2e_agent_test.db"
    if db_path.exists():
        db_path.unlink()
    (BACKEND / "data").mkdir(parents=True, exist_ok=True)

    env = {
        **os.environ,
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite:///./data/e2e_agent_test.db",
        "AUTO_SEED_DEMO_USERS": "true",
        "AUTO_IMPORT_DEMO": "false",
        "LLM_PROVIDER": "none",
        "AGENT_ALLOW_MOCK_PROVIDERS": "true",
        "JWT_SECRET": "e2e_agent_golden_path_secret_only_for_test_0123456789",
        "CORS_ORIGINS": "http://127.0.0.1:*,http://localhost:*",
        "PYTHONPATH": str(BACKEND),
    }
    kwargs = {"cwd": str(BACKEND), "stdout": None, "stderr": subprocess.STDOUT, "env": env}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        **kwargs,
    )


def start_frontend(port, backend_port):
    """启动 Vite dev,代理到后端端口。"""
    node = shutil.which("node")
    vite = WEBREACT / "node_modules" / "vite" / "bin" / "vite.js"
    if not node:
        raise RuntimeError("未找到 node 可执行文件")
    if not vite.exists():
        raise RuntimeError(f"未找到 Vite 入口: {vite};请先安装 webreact 依赖")
    env = {**os.environ, "VITE_BACKEND_PORT": str(backend_port)}
    kwargs = {"cwd": str(WEBREACT), "stdout": None, "stderr": subprocess.STDOUT, "env": env}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(
        [node, str(vite), "--port", str(port), "--strictPort", "--host", "127.0.0.1"],
        **kwargs,
    )


def main():
    parser = argparse.ArgumentParser(description="Agent 三条黄金路径 E2E")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--final-review-only", action="store_true", help="只执行期末复习路径")
    group.add_argument("--notice-only", action="store_true", help="只执行通知事务路径")
    group.add_argument("--course-research-only", action="store_true", help="只执行课程研究路径")
    args = parser.parse_args()

    if args.final_review_only:
        selected = ["final-review"]
    elif args.notice_only:
        selected = ["notice"]
    elif args.course_research_only:
        selected = ["course-research"]
    else:
        selected = ["final-review", "notice", "course-research"]

    for name in selected:
        if not SCRIPTS[name].exists():
            print(f"错误: 缺少 E2E 脚本 {SCRIPTS[name]}", file=sys.stderr)
            return 2

    backend_port = find_free_port(BASE_BACKEND_PORT)
    frontend_port = find_free_port(BASE_FRONTEND_PORT)
    print(f"启动后端(fake provider)端口 {backend_port},前端端口 {frontend_port}")

    backend_proc = None
    frontend_proc = None
    exit_code = 0
    try:
        try:
            backend_proc = start_backend(backend_port)
            wait_for_http(f"http://127.0.0.1:{backend_port}/", timeout=START_TIMEOUT_SECONDS)
        except Exception as exc:
            print(f"错误: 后端启动失败: {exc}", file=sys.stderr)
            return 2
        print(f"后端已就绪: http://127.0.0.1:{backend_port}/")

        try:
            frontend_proc = start_frontend(frontend_port, backend_port)
            wait_for_http(f"http://127.0.0.1:{frontend_port}/", timeout=START_TIMEOUT_SECONDS)
        except Exception as exc:
            print(f"错误: 前端启动失败: {exc}", file=sys.stderr)
            return 2
        print(f"前端已就绪: http://127.0.0.1:{frontend_port}/")

        env = {
            **os.environ,
            "WEB_BASE_URL": f"http://127.0.0.1:{frontend_port}",
            "API_BASE_URL": f"http://127.0.0.1:{backend_port}/api/v1",
            "DEMO_USERNAME": DEMO_USERNAME,
            "DEMO_PASSWORD": DEMO_PASSWORD,
        }
        failures = []
        for name in selected:
            print(f"执行 {SCRIPTS[name].name}")
            result = subprocess.run([sys.executable, str(SCRIPTS[name])], env=env)
            if result.returncode != 0:
                failures.append(SCRIPTS[name].name)
        if failures:
            print(f"失败: {', '.join(failures)}", file=sys.stderr)
            exit_code = 1
    finally:
        if frontend_proc is not None:
            stop_process_tree(frontend_proc)
        if backend_proc is not None:
            stop_process_tree(backend_proc)
        for port in (frontend_port, backend_port):
            if wait_for_port_release(port):
                print(f"端口 {port} 已释放")
            else:
                print(f"错误: 端口 {port} 仍被占用", file=sys.stderr)
                exit_code = 1
    if exit_code == 0:
        print("ALL AGENT GOLDEN PATH CHECKS PASSED")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())