"""magicclass 课程页 E2E 入口：拉起隔离的三服务，跑真实浏览器验收，最后回收。

用法（从仓库根目录）：

    backend/.venv/Scripts/python.exe webreact/tests/e2e/run_magicclass_courses_e2e.py

为什么需要它：单测可以全绿而真实链路仍然 503 —— 只要配置、端口或进程没对上。
所以这里启动的是**真的三个进程**：

    Vite (5174 段)  →  FastAPI (8000 段)  →  magicclass-service (4010 段)

隔离措施：
- 后端数据库复制一份到临时目录，不动 `backend/data/app.db`；
- 受管服务用临时 SQLite 文件；
- 内部断言密钥在进程内随机生成，只经环境变量注入，不落盘、不打印；
- 端口全部按空闲探测，避免和开发中的服务抢端口。
"""

from __future__ import annotations

import os
import json
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEBREACT = HERE.parent.parent
REPO = WEBREACT.parent
BACKEND = REPO / "backend"
SERVICE = REPO / "magicclass-service"

START_TIMEOUT_SECONDS = 90
MAX_PORT_TRIES = 12


def find_free_port(start: int) -> int:
    for port in range(start, start + MAX_PORT_TRIES):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _opener():
    # 本机回环调用绝不能被开发机的 HTTP 代理接管。
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http_status(url: str, timeout: float = 3.0) -> int | None:
    try:
        with _opener().open(url, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception:
        return None


def wait_for(url: str, *, label: str, timeout: float = START_TIMEOUT_SECONDS, expect: int = 200) -> None:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = http_status(url)
        if last == expect:
            return
        time.sleep(1)
    raise RuntimeError(f"{label} 在 {timeout}s 内未就绪（{url}），最后一次状态：{last}")


def port_is_free(port: int) -> bool:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def wait_for_port_release(port: int, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_is_free(port):
            return True
        time.sleep(0.2)
    return False


def _popen(argv, *, cwd: Path, env: dict, log_file: Path | None = None) -> subprocess.Popen:
    """启动子进程。

    输出**不能**丢进 DEVNULL：真实链路的失败原因几乎都在子进程的 stderr 里，
    吞掉它就等于把"为什么 503"重新变成猜测。
    """
    stream = open(log_file, "wb") if log_file else subprocess.DEVNULL
    kwargs = {"cwd": str(cwd), "env": env, "stdout": stream, "stderr": subprocess.STDOUT}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen([str(item) for item in argv], **kwargs)


def dump_logs(logs: dict[str, Path]) -> None:
    for label, path in logs.items():
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue
        print(f"\n--- {label} 日志（末 40 行）---")
        print("\n".join(text.splitlines()[-40:]))


def stop_process_tree(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def resolve_python() -> Path:
    """跑 FastAPI 的解释器：优先仓库内 venv，保证 fastapi/uvicorn 可用。"""
    for candidate in (BACKEND / ".venv" / "Scripts" / "python.exe", BACKEND / ".venv" / "bin" / "python"):
        if candidate.exists():
            return candidate
    return Path(sys.executable)


def resolve_node() -> str:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("PATH 中找不到 node（magicclass-service 需要 Node >= 22.19）")
    return node


class ServiceControl:
    """受管服务的生命周期，供浏览器检查在"掉线 / 恢复"场景里调用。"""

    def __init__(self, argv, cwd: Path, env: dict, port: int, log_file: Path) -> None:
        self.argv = argv
        self.cwd = cwd
        self.env = env
        self.port = port
        self.log_file = log_file
        self.proc: subprocess.Popen | None = None

    def start(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            return
        self.proc = _popen(self.argv, cwd=self.cwd, env=self.env, log_file=self.log_file)
        wait_for(f"http://127.0.0.1:{self.port}/internal/health/live", label="magicclass-service", timeout=45)

    def stop(self) -> None:
        stop_process_tree(self.proc)
        self.proc = None
        if not wait_for_port_release(self.port):
            raise RuntimeError(f"受管服务端口 {self.port} 未被释放")


class MockGenerationProvider:
    """仅供 E2E 使用的本地 OpenAI 兼容生成端点。

    网关故意拒绝未配置模型时的 ``local-template`` 结果。这里用回环服务器返回一份
    通过受管服务质量门的模型形状，让浏览器验收覆盖真实的
    Vite → FastAPI → magicclass-service → provider 请求链，而不使用真实密钥。
    """

    _DOCUMENT = {
        "dslVersion": "0.3.0",
        "stage": {"name": "E2E 学习课堂", "description": "隔离浏览器验收使用的受管生成结果。"},
        "scenes": [
            {
                "title": "概念解释",
                "order": 0,
                "type": "slide",
                "content": {
                    "type": "slide",
                    "slide": {
                        "title": "理解核心概念",
                        "sections": [{"heading": "概念解释", "bullets": ["先明确概念的定义、适用条件与解决的问题，再用课程资料检验理解是否准确。"]}],
                    },
                },
            },
            {
                "title": "推导与例子",
                "order": 1,
                "type": "slide",
                "content": {
                    "type": "slide",
                    "slide": {
                        "title": "推导与例子",
                        "sections": [{"heading": "推导步骤", "bullets": ["从已知条件出发，逐步选择关系式、代入可核对的量，并检查结论是否符合概念的适用范围。"]}],
                    },
                },
            },
            {
                "title": "课堂自测",
                "order": 2,
                "type": "quiz",
                "content": {
                    "type": "quiz",
                    "questions": [
                        {
                            "type": "single",
                            "question": "开始学习一个新概念时，最合理的第一步是什么？",
                            "options": [
                                {"label": "明确概念的定义与适用条件", "value": "A"},
                                {"label": "跳过概念直接记结论", "value": "B"},
                                {"label": "只记录例题的最终答案", "value": "C"},
                            ],
                            "answer": ["A"],
                            "analysis": "先理解定义和适用条件，才能用例子检验结论。",
                            "points": 1,
                        },
                    ],
                },
            },
        ],
    }

    def __init__(self) -> None:
        document = self._DOCUMENT

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format, *_args):  # noqa: N802 - stdlib hook
                return

            def do_POST(self):  # noqa: N802 - stdlib hook
                if self.path != "/chat/completions":
                    self.send_error(404)
                    return
                length = int(self.headers.get("content-length", "0"))
                try:
                    json.loads(self.rfile.read(length).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self.send_error(400)
                    return
                response = json.dumps({"choices": [{"message": {"content": json.dumps(document, ensure_ascii=False)}}]}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("content-type", "application/json; charset=utf-8")
                self.send_header("content-length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


def provision_databases(root: Path) -> tuple[Path, Path]:
    """复制一份真实后端库到临时目录；受管服务用全新库。"""
    backend_db = root / "app.db"
    source = BACKEND / "data" / "app.db"
    if source.exists():
        for suffix in ("", "-wal", "-shm"):
            part = source.with_name(source.name + suffix)
            if part.exists():
                shutil.copy2(part, backend_db.with_name(backend_db.name + suffix))
        print(f"  已复制真实后端库快照 → {backend_db.name}")
    else:
        print("  未找到 backend/data/app.db，将用全新库（启动时会自动 seed 演示数据）")
    return backend_db, root / "magicclass-service.db"


def main() -> int:
    # Windows CI/desktop shells may use GBK; the subprocess logs contain Unicode
    # service diagnostics, so never let report printing hide the real E2E failure.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(errors="replace")
    node = resolve_node()
    python = resolve_python()
    tmp_root = Path(tempfile.mkdtemp(prefix="campusmate-magicclass-e2e-"))
    print(f"隔离临时目录：{tmp_root}")

    backend_db, service_db = provision_databases(tmp_root)
    secret = secrets.token_urlsafe(36)
    provider = MockGenerationProvider()
    provider.start()

    service_port = find_free_port(4110)
    backend_port = find_free_port(8011)
    web_port = find_free_port(5184)

    # 本机回环 + 子进程都绕开开发机代理，避免"服务起来了却连不上"。
    base_env = {**os.environ, "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"}

    service_env = {
        **base_env,
        "MAGICCLASS_HOST": "127.0.0.1",
        "MAGICCLASS_PORT": str(service_port),
        "MAGICCLASS_DATABASE_URL": str(service_db),
        "MAGICCLASS_INTERNAL_SECRET": secret,
        "MAGICCLASS_PROVIDER_BASE_URL": provider.base_url,
        "MAGICCLASS_PROVIDER_API_KEY": "e2e-local-test-key",
        "MAGICCLASS_PROVIDER_MODEL": "e2e-local-test-model",
    }
    backend_env = {
        **base_env,
        "DATABASE_URL": f"sqlite:///{backend_db.as_posix()}",
        "MAGICCLASS_FUSION_ENABLED": "true",
        "MAGICCLASS_SERVICE_URL": f"http://127.0.0.1:{service_port}",
        "MAGICCLASS_INTERNAL_SECRET": secret,
        "MAGICCLASS_SERVICE_TIMEOUT_SECONDS": "5",
        "MAGICCLASS_ENABLED": "false",
        "AUTO_SEED_DEMO_USERS": "true",
        "LOG_LEVEL": "WARNING",
    }

    service = ServiceControl(
        [node, "--experimental-strip-types", "src/main.ts"], SERVICE, service_env, service_port,
        tmp_root / "magicclass-service.log",
    )
    logs = {
        "magicclass-service": tmp_root / "magicclass-service.log",
        "FastAPI": tmp_root / "fastapi.log",
        "Vite": tmp_root / "vite.log",
    }
    backend = None
    vite = None
    exit_code = 0
    try:
        print(f"启动 magicclass-service :{service_port}")
        service.start()
        print(f"启动 FastAPI          :{backend_port}")
        backend = _popen(
            [python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(backend_port), "--log-level", "warning"],
            cwd=BACKEND, env=backend_env, log_file=logs["FastAPI"],
        )
        wait_for(f"http://127.0.0.1:{backend_port}/api/v1/health", label="FastAPI")

        print(f"启动 Vite             :{web_port}")
        vite = _popen(
            [node, str(WEBREACT / "node_modules" / "vite" / "bin" / "vite.js"), "--port", str(web_port), "--strictPort", "--host", "127.0.0.1"],
            cwd=WEBREACT, env={**base_env, "VITE_BACKEND_PORT": str(backend_port)}, log_file=logs["Vite"],
        )
        wait_for(f"http://127.0.0.1:{web_port}/", label="Vite")

        base_url = f"http://127.0.0.1:{web_port}"
        print(f"三服务就绪，浏览器验收目标：{base_url}\n")

        os.environ["WEB_BASE_URL"] = base_url
        os.environ["E2E_SHOTS_DIR"] = str(tmp_root / "shots")
        sys.path.insert(0, str(HERE))
        import magicclass_courses_browser  # noqa: E402  （必须在 WEB_BASE_URL 之后导入）

        result = magicclass_courses_browser.run_checks(service)
        print("\n===== 浏览器验收报告 =====")
        for line in result["report"]:
            print(f"  · {line}")
        print("  · 截图：" + "、".join(Path(p).name for p in result["shots"]))
        print("\nALL MAGICCLASS COURSES E2E CHECKS PASSED")
    except Exception as exc:  # noqa: BLE001 - 入口脚本要把失败原因完整打出来
        print(f"\nE2E 失败：{type(exc).__name__}: {exc}", file=sys.stderr)
        dump_logs(logs)
        exit_code = 1
    finally:
        stop_process_tree(vite)
        stop_process_tree(backend)
        service.stop()
        provider.stop()
        for port, label in ((web_port, "Vite"), (backend_port, "FastAPI"), (service_port, "magicclass-service")):
            if wait_for_port_release(port, timeout=5):
                print(f"{label} 已回收，端口 {port} 已释放")
            else:
                print(f"错误：{label} 退出后端口 {port} 仍被占用", file=sys.stderr)
                exit_code = 1
        shutil.rmtree(tmp_root, ignore_errors=True)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
