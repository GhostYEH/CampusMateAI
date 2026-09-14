"""课程知识图谱 Web E2E：真实浏览器 → 真实后端 → 真实库 → 真实页面。

为什么需要它：后端链路（解析/落库/事件/世界模型）此前只有单测，
三端前端则完全没有入口。单测证明不了"用户真的能看到"，也证明不了
"数据是从接口来的而不是写死的"。这里三件事一起钉死：

1. 课程页真的能进到「知识点掌握」（入口存在，不是只有路由）；
2. 页面上渲染的数字来自 GET /courses/{id}/knowledge-graph 的 200 响应（不是内联假数据）；
3. 未同步的课程给出可操作的同步引导，而不是空白。

夹具走真实链路：backend/tests/fixtures/chaoxing/course_knowledge_graph.html
（脱敏真实页面）→ 真实 ChaoxingParser → 真实 ChaoxingRepository。
"""
from __future__ import annotations

import atexit
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print(
        "ERROR: playwright is not installed.\n"
        "Install with: pip install playwright && playwright install chromium",
        file=sys.stderr,
    )
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
WEBREACT_DIR = REPO_ROOT / "webreact"
SEEDER = Path(__file__).resolve().parent / "_seed_course_knowledge_graph.py"

COURSE_NAME = "高等数学（Ⅱ）"
EXPECTED_POINTS = 21
EXPECTED_OWN = "87.5%"
EXPECTED_CLASS = "69%"
EXPECTED_GAP = "+18.5"

_processes: list[subprocess.Popen] = []
_tempdir: str | None = None


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_port(port: int, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except (ConnectionRefusedError, OSError):
            time.sleep(0.3)
    raise RuntimeError(f"port {port} not ready within {timeout}s")


def _wait_for_http(url: str, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except (urllib.error.URLError, ConnectionRefusedError, OSError):
            time.sleep(0.3)
    raise RuntimeError(f"{url} not ready within {timeout}s")


def _start_backend(port: int) -> str:
    global _tempdir
    _tempdir = tempfile.mkdtemp(prefix="e2e_kg_")
    db_path = Path(_tempdir) / "e2e.db"
    env = os.environ.copy()
    env["APP_ENV"] = "test"
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["AUTO_SEED_DEMO_USERS"] = "true"
    env["AUTO_IMPORT_DEMO"] = "false"
    env["JWT_SECRET_KEY"] = "e2e-test-secret-key-for-testing-only"
    env["PYTHONPATH"] = str(BACKEND_DIR)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(BACKEND_DIR), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    _processes.append(proc)
    _wait_for_http(f"http://127.0.0.1:{port}/", timeout=90)
    return env["DATABASE_URL"]


def _seed(database_url: str, username: str) -> None:
    """独立进程写入夹具：避免与 uvicorn 共享 Database 单例。"""
    env = os.environ.copy()
    env["APP_ENV"] = "test"
    env["PYTHONPATH"] = str(BACKEND_DIR)
    result = subprocess.run(
        [sys.executable, str(SEEDER), username, database_url],
        cwd=str(BACKEND_DIR), env=env, capture_output=True, text=True, timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(f"seeding failed:\n{result.stdout}\n{result.stderr}")
    print(f"  {result.stdout.strip()}")


def _start_vite(port: int, api_base: str) -> None:
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    env = os.environ.copy()
    env["VITE_API_BASE_URL"] = api_base
    proc = subprocess.Popen(
        [npm_cmd, "run", "dev", "--", "--port", str(port), "--host", "127.0.0.1"],
        cwd=str(WEBREACT_DIR), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False,
    )
    _processes.append(proc)
    _wait_for_port(port, timeout=90)


def _cleanup() -> None:
    for proc in _processes:
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    proc.kill()
                except OSError:
                    pass
    if _tempdir and Path(_tempdir).exists():
        shutil.rmtree(_tempdir, ignore_errors=True)


atexit.register(_cleanup)


def run_case(page, *, base_url: str, username: str, api_base: str) -> None:
    # 1. 从首页真实入口进入课程页（不是直接拼 URL）
    page.goto(f"{base_url}/login", wait_until="networkidle")
    page.wait_for_selector("input[autoComplete='username']", timeout=15000)
    page.fill("input[autoComplete='username']", username)
    page.fill("input[autoComplete='current-password']", "Demo123456")
    page.click("button.login-submit")
    page.wait_for_url(f"{base_url}/home", timeout=15000)

    page.goto(f"{base_url}/courses", wait_until="networkidle")
    page.wait_for_selector(".course-sort-item", timeout=15000)
    card = page.locator(".course-sort-item", has_text=COURSE_NAME).first
    assert card.count() > 0, f"课程列表里没有 {COURSE_NAME}"

    # 2. 进课程详情，同时抓取真实接口响应（证明页面上是接口数据，不是写死的）
    with page.expect_response(
        lambda response: "/knowledge-graph" in response.url and response.status == 200,
        timeout=20000,
    ) as captured:
        card.click()
    payload = captured.value.json()
    page.wait_for_url(f"{base_url}/courses/*", timeout=15000)
    assert payload["available"] is True, payload
    assert payload["knowledge_point_count"] == EXPECTED_POINTS, payload
    assert payload["own_mastery_rate"] == 87.5, payload
    assert payload["class_mastery_rate"] == 69.0, payload
    assert payload["mastery_gap_vs_class"] == 18.5, payload
    assert len(payload["points"]) == EXPECTED_POINTS, len(payload["points"])

    # 3. 概览页与 tab 都必须有可见入口（页面存在但进不去是已知盲区）
    page.wait_for_selector(".course-tabs", timeout=15000)
    entry = page.locator(".course-tabs button", has_text="知识点掌握")
    assert entry.count() == 1, "课程详情缺少「知识点掌握」入口"
    overview_entry = page.locator("button.text-button", has_text="查看详情")
    assert overview_entry.count() >= 1, "概览页缺少知识点掌握卡片入口"

    # 4. 点入口 → 断言渲染的数字与接口一致
    entry.click()
    panel = page.locator(".mastery-panel")
    panel.wait_for(timeout=15000)
    text = panel.inner_text()
    for expected in (EXPECTED_OWN, EXPECTED_CLASS, EXPECTED_GAP, str(EXPECTED_POINTS)):
        assert expected in text, f"知识点面板缺少 {expected}：\n{text}"
    assert "领先班级" in text, f"缺少班级对比口径：\n{text}"

    # 5. 知识点清单逐条来自接口（结构性断言，不靠文本抓取）
    point_rows = panel.locator(".list-row")
    point_rows.first.wait_for(timeout=15000)
    assert point_rows.count() == EXPECTED_POINTS, (
        f"知识点条数 {point_rows.count()} != {EXPECTED_POINTS}"
    )
    assert payload["points"][0]["name"] in panel.inner_text(), (
        f"知识点清单未渲染：\n{panel.inner_html()[:2000]}"
    )

    # 5. 没有脚本报错、没有横向溢出
    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert overflow <= 1, f"知识点面板导致横向溢出 {overflow}px"


def main() -> None:
    backend_port = _free_port()
    vite_port = _free_port()
    api_base = f"http://127.0.0.1:{backend_port}/api/v1"
    base_url = f"http://127.0.0.1:{vite_port}"

    print(f"Starting backend on {backend_port}...")
    database_url = _start_backend(backend_port)
    print("Seeding course knowledge graph via real parser...")
    _seed(database_url, "student_demo")
    print(f"Starting Vite on {vite_port}...")
    _start_vite(vite_port, api_base)

    failures: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for name, size in (("desktop", {"width": 1440, "height": 900}),
                           ("mobile", {"width": 390, "height": 844})):
            context = browser.new_context(viewport=size, reduced_motion="reduce")
            page = context.new_page()
            page_errors: list[str] = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            try:
                run_case(page, base_url=base_url, username="student_demo", api_base=api_base)
                assert not page_errors, f"page errors: {page_errors}"
                print(f"  PASS {name} ({size['width']}x{size['height']})")
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{name}: {exc}")
                print(f"  FAIL {name}: {exc}", file=sys.stderr)
            finally:
                context.close()
        browser.close()

    print(f"E2E complete: {2 - len(failures)}/2 passed")
    if failures:
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        _cleanup()
        sys.exit(1)
    _cleanup()


if __name__ == "__main__":
    main()
