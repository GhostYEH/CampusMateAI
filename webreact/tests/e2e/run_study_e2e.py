"""学习弹窗 E2E 入口: 自动启动 Vite dev 服务,执行 Playwright 检查后回收进程。

用法:
    cd webreact && python tests/e2e/run_study_e2e.py
    cd webreact && python tests/e2e/run_study_e2e.py --focus-only
    cd webreact && python tests/e2e/run_study_e2e.py --viewports-only

行为:
- 在 5174 起按顺序探测空闲端口(最多试 10 个),不再写死单一端口。
- 用 Node 直接启动 Vite,等待 / 返回 200。
- 设置 WEB_BASE_URL 后依次执行 study-dialogs-modal-focus.py 与
  study-dialogs-viewports.py,任一失败即整体失败。
- 成功或失败都会终止 Vite 进程,不残留。
- Vite 启动失败或超时输出明确错误,不吞异常。
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
BASE_PORT = int(os.environ.get("STUDY_E2E_PORT", "5174"))
MAX_TRIES = 10
START_TIMEOUT_SECONDS = 60

SCRIPTS = {
    "focus": HERE / "study-dialogs-modal-focus.py",
    "viewports": HERE / "study-dialogs-viewports.py",
}


def find_free_port(start):
    for port in range(start, start + MAX_TRIES):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    # 顺序端口段全被占用(如多会话并行开发)时,让系统分配一个空闲端口。
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", 0))
        except OSError as exc:
            raise RuntimeError(f"在 {start} 起连续 {MAX_TRIES} 个端口均被占用,且系统无空闲端口: {exc}")
        return sock.getsockname()[1]


def wait_for_vite(port):
    url = f"http://127.0.0.1:{port}/"
    deadline = time.time() + START_TIMEOUT_SECONDS
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    return
                last_error = f"Vite 返回非 200 状态: {response.status}"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(1)
    raise RuntimeError(f"Vite 在 {START_TIMEOUT_SECONDS}s 内未就绪({url}),最后错误: {last_error}")


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


def start_vite(port):
    node = shutil.which("node")
    vite = WEBREACT / "node_modules" / "vite" / "bin" / "vite.js"
    if not node:
        raise RuntimeError("未找到 node 可执行文件")
    if not vite.exists():
        raise RuntimeError(f"未找到 Vite 入口: {vite};请先安装 webreact 依赖")
    kwargs = {"cwd": str(WEBREACT), "stdout": None, "stderr": subprocess.STDOUT}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(
        [node, str(vite), "--port", str(port), "--strictPort", "--host", "127.0.0.1"],
        **kwargs,
    )


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
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            proc.kill()
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        proc.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description="学习弹窗 E2E: 自动起服并执行 Playwright 检查")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--focus-only", action="store_true", help="只执行 Modal 焦点行为检查")
    group.add_argument("--viewports-only", action="store_true", help="只执行多视口弹窗检查")
    args = parser.parse_args()

    if args.focus_only:
        selected = ["focus"]
    elif args.viewports_only:
        selected = ["viewports"]
    else:
        selected = ["focus", "viewports"]

    for name in selected:
        if not SCRIPTS[name].exists():
            print(f"错误: 缺少 E2E 脚本 {SCRIPTS[name]}", file=sys.stderr)
            return 2

    try:
        port = find_free_port(BASE_PORT)
    except RuntimeError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2
    print(f"启动 Vite dev 服务,端口 {port}")

    try:
        proc = start_vite(port)
    except RuntimeError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2
    exit_code = 0
    try:
        try:
            wait_for_vite(port)
        except RuntimeError as exc:
            print(f"错误: {exc}", file=sys.stderr)
            exit_code = 2
        else:
            print(f"Vite 已就绪: http://127.0.0.1:{port}/")
            env = {**os.environ, "WEB_BASE_URL": f"http://127.0.0.1:{port}"}
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
        stop_process_tree(proc)
        if wait_for_port_release(port):
            print("Vite dev 服务已回收,端口已释放")
        else:
            print(f"错误: Vite 退出后端口 {port} 仍被占用", file=sys.stderr)
            exit_code = 1
    if exit_code == 0:
        print("ALL STUDY E2E CHECKS PASSED")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
