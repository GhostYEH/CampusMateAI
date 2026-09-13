"""Phase 6D: 学习状态页面 E2E 闭环测试。

自动启动独立测试数据库后端和 Vite，执行完整 20 步骤闭环：
登录 → 打开学习状态 → 查看 CORE/KNOWLEDGE evidence → 提交并撤销纠正 →
暂停并恢复 PRACTICE → 生成、接受、执行计划 → 查看 evaluation →
提交 feedback → 删除 MODEL_SHADOW_ONLY → 验证账号及其他状态仍存在

覆盖桌面和移动端，无横向溢出、无 pageerror。
任何失败必须非零退出；缺少 Playwright 也不能伪通过。
测试结束必须可靠关闭服务并清理演示数据库。
"""
from __future__ import annotations

import atexit
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print(
        "ERROR: playwright is not installed.\n"
        "Install with: pip install playwright && playwright install chromium\n"
        "or: npm install -D playwright && npx playwright install chromium",
        file=sys.stderr,
    )
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
WEBREACT_DIR = REPO_ROOT / "webreact"
BACKEND_PORT = 8765
VITE_PORT = 5174
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
BASE_URL = f"http://127.0.0.1:{VITE_PORT}"
API_BASE = f"{BACKEND_URL}/api/v1"

VIEWPORTS = [
    {"width": 1440, "height": 900, "name": "desktop", "username": "student_demo"},
    {"width": 390, "height": 844, "name": "mobile", "username": "student_demo_01"},
]

_processes: list[subprocess.Popen] = []
_tempdir: str | None = None


def _wait_for_port(port: int, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except (ConnectionRefusedError, OSError):
            time.sleep(0.3)
    raise RuntimeError(f"port {port} not ready within {timeout}s")


def _wait_for_http(url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except (urllib.error.URLError, ConnectionRefusedError, OSError):
            time.sleep(0.3)
    raise RuntimeError(f"{url} not ready within {timeout}s")


def _start_backend() -> None:
    global _tempdir
    _tempdir = tempfile.mkdtemp(prefix="e2e_learnstate_")
    db_path = Path(_tempdir) / "e2e.db"
    env = os.environ.copy()
    env["APP_ENV"] = "test"
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["AUTO_SEED_DEMO_USERS"] = "true"
    env["JWT_SECRET_KEY"] = "e2e-test-secret-key-for-testing-only"
    env["PYTHONPATH"] = str(BACKEND_DIR)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(BACKEND_PORT)],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    _processes.append(proc)
    _wait_for_http(f"{BACKEND_URL}/", timeout=40)


def _start_vite() -> None:
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    env = os.environ.copy()
    env["VITE_API_BASE_URL"] = API_BASE
    proc = subprocess.Popen(
        [npm_cmd, "run", "dev", "--", "--port", str(VITE_PORT), "--host", "127.0.0.1"],
        cwd=str(WEBREACT_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=False,
    )
    _processes.append(proc)
    _wait_for_port(VITE_PORT, timeout=40)


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


def _api_login(page, username: str, password: str) -> str:
    """Login via API and return an access token for direct seed requests."""
    resp = page.request.post(f"{API_BASE}/auth/login", data={"username": username, "password": password})
    assert resp.status == 200, f"login failed: {resp.status} {resp.text()}"
    body = resp.json()
    token = body["access_token"]
    return token


def _api_post(page, path: str, token: str, data: dict | None = None) -> dict:
    resp = page.request.post(
        f"{API_BASE}{path}",
        data=data or {},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status < 400, f"POST {path} failed: {resp.status} {resp.text()}"
    return resp.json() if resp.text() else {}


def _api_get(page, path: str, token: str) -> dict:
    resp = page.request.get(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status < 400, f"GET {path} failed: {resp.status} {resp.text()}"
    return resp.json()


def _seed_learner_data(page, token: str) -> None:
    """Seed study sessions and learner events for the demo student via API."""
    for i in range(3):
        create_resp = page.request.post(
            f"{API_BASE}/study/sessions",
            data={"goal": f"复习数据结构第{i+1}章", "duration_minutes": 30 + i * 10},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status < 400, f"seed session failed: {create_resp.status} {create_resp.text()}"
        session = create_resp.json()
        session_id = session.get("session_id") or session.get("id")
        assert session_id, f"seed session missing id: {session}"
        finish_resp = page.request.post(
            f"{API_BASE}/study/sessions/{session_id}/finish",
            data={"self_report": "完成了一些练习题", "duration_minutes": 30 + i * 10},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert finish_resp.status < 400, f"finish session failed: {finish_resp.status} {finish_resp.text()}"


def _assert_evidence(body: dict, label: str, require_items: bool) -> None:
    for field in ("items", "total", "page", "page_size", "has_more"):
        assert field in body, f"{label} evidence missing {field}: {body}"
    assert isinstance(body["items"], list), f"{label} evidence items must be a list"
    if require_items:
        assert body["items"], f"{label} evidence items empty"
    for item in body["items"]:
        for field in ("evidence_kind", "source_category", "role", "explanation_code"):
            assert item.get(field), f"{label} evidence missing safe field {field}: {item}"
        for forbidden in ("source_id", "table_name", "payload", "prompt", "source_text", "answer"):
            assert forbidden not in item, f"{label} evidence leaks {forbidden}: {item}"


def _check_no_overflow(page, viewport_name: str) -> None:
    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    client_width = page.evaluate("document.documentElement.clientWidth")
    assert scroll_width <= client_width + 1, f"horizontal overflow at {viewport_name}: {scroll_width} > {client_width}"


def run_closed_loop(page, viewport, token: str) -> None:
    """执行完整闭环测试。任一断言失败抛异常。"""
    vp_name = viewport["name"]
    page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})

    # 1. 登录
    page.goto(f"{BASE_URL}/login", wait_until="networkidle")
    page.wait_for_selector("input[autoComplete='username']", timeout=10000)
    page.fill("input[autoComplete='username']", viewport["username"])
    page.fill("input[autoComplete='current-password']", "Demo123456")
    page.click("button.login-submit")
    try:
        page.wait_for_url(f"{BASE_URL}/home", timeout=10000)
    except Exception as exc:
        alert = page.locator("[role='alert']")
        detail = alert.inner_text() if alert.count() else "no login error rendered"
        raise AssertionError(f"UI login did not navigate: {detail}") from exc

    # 2. 打开学习状态页面
    page.goto(f"{BASE_URL}/learning-state", wait_until="networkidle")
    page.wait_for_selector(".learning-state-page", timeout=15000)

    # 3. 验证页面标题
    title = page.query_selector(".ls-title")
    assert title is not None, "title element not found"
    assert "学习状态" in title.inner_text(), f"unexpected title: {title.inner_text()}"

    # 4. 验证无横向溢出
    _check_no_overflow(page, vp_name)

    # 5. Seed learner data via API and refresh
    _seed_learner_data(page, token)
    page.reload(wait_until="networkidle")
    page.wait_for_selector(".learning-state-page", timeout=15000)

    # 6. 查看 CORE evidence — 点击第一个"查看依据"按钮
    view_evidence_btns = page.query_selector_all(".ls-state-card .ls-link-btn")
    assert view_evidence_btns, "no CORE evidence button"
    core_page = _api_get(page, "/learner-state/snapshots?scope_type=USER&page=1&page_size=50", token)
    assert core_page.get("items"), f"no CORE snapshots: {core_page}"
    core_snapshot_id = core_page["items"][0].get("snapshot_id")
    assert core_snapshot_id, f"CORE snapshot missing id: {core_page['items'][0]}"
    core_evidence = _api_get(
        page, f"/learner-state/snapshots/{core_snapshot_id}/evidence?page=1&page_size=20", token
    )
    _assert_evidence(core_evidence, "CORE", True)
    view_evidence_btns[0].click()
    page.wait_for_selector(".ls-drawer", timeout=5000)
    assert page.query_selector(".ls-drawer") is not None, "evidence drawer did not open"

    courses = _api_get(page, "/courses?page=1&page_size=20", token)
    course_items = courses.get("items", courses) if isinstance(courses, dict) else courses
    assert course_items, f"no courses for KNOWLEDGE evidence: {courses}"
    course_id = course_items[0].get("id") or course_items[0].get("course_id")
    assert course_id, f"course missing id: {course_items[0]}"
    knowledge = _api_get(page, f"/learner-state/knowledge?course_id={course_id}", token)
    assert isinstance(knowledge, list) and knowledge, f"no knowledge snapshots: {knowledge}"
    knowledge_snapshot_id = knowledge[0].get("snapshot_id")
    assert knowledge_snapshot_id, f"knowledge snapshot missing id: {knowledge[0]}"
    knowledge_evidence = _api_get(
        page, f"/learner-state/snapshots/{knowledge_snapshot_id}/evidence?page=1&page_size=20", token
    )
    _assert_evidence(knowledge_evidence, "KNOWLEDGE", False)

    # 7. 提交纠正
    correction_opts = page.query_selector_all(".ls-correction-options .ls-btn")
    assert correction_opts, "no correction options in evidence drawer"
    correction_opts[0].click()
    submit_btn = page.query_selector(".ls-drawer__correction .ls-btn--primary")
    assert submit_btn is not None and submit_btn.is_enabled(), "correction submit unavailable"
    submit_btn.click()
    page.wait_for_timeout(1000)

    # 8. 撤销纠正
    page.reload(wait_until="networkidle")
    page.wait_for_selector(".learning-state-page", timeout=10000)
    revoke_btns = page.query_selector_all(".ls-correction-row .ls-btn")
    assert revoke_btns, "no correction record to revoke"
    revoke_btns[0].click()
    page.wait_for_timeout(1000)

    # 9. 暂停 PRACTICE 数据源
    page.reload(wait_until="networkidle")
    page.wait_for_selector(".learning-state-page", timeout=10000)
    source_rows = page.query_selector_all(".ls-source-row")
    practice_row = None
    for row in source_rows:
        name_el = row.query_selector(".ls-source-row__name")
        if name_el and "练习" in name_el.inner_text():
            practice_row = row
            break
    assert practice_row is not None, "PRACTICE source row not found"
    pause_btn = practice_row.query_selector(".ls-btn:has-text('暂停')")
    assert pause_btn is not None, "PRACTICE pause button not found"
    pause_btn.click()
    page.wait_for_timeout(1000)
    _check_no_overflow(page, vp_name)

    # 10. 恢复 PRACTICE
    resume_btn = practice_row.query_selector(".ls-btn:has-text('恢复')")
    assert resume_btn is not None, "PRACTICE resume button not found"
    resume_btn.click()
    page.wait_for_timeout(1000)

    # 11. 生成计划 via API
    plan = _api_post(page, "/learning-plans/generate", token, {"available_minutes": 60})
    assert plan.get("plan_id") or plan.get("id"), f"plan generate missing id: {plan}"

    # 12. 刷新页面查看计划
    plan_id = plan.get("plan_id") or plan.get("id")
    page.reload(wait_until="networkidle")
    page.wait_for_selector(".learning-state-page", timeout=10000)
    _check_no_overflow(page, vp_name)

    # 13. 接受计划
    accept_btn = page.query_selector(".ls-plan .ls-btn--primary:has-text('接受计划')")
    assert accept_btn is not None, "accept plan button not found"
    accept_btn.click()
    page.wait_for_timeout(1000)

    # 14. 执行计划
    page.reload(wait_until="networkidle")
    page.wait_for_selector(".learning-state-page", timeout=10000)
    execute_btn = page.query_selector(".ls-plan .ls-btn--primary:has-text('创建个人学习任务')")
    assert execute_btn is not None, "execute plan button not found"
    execute_btn.click()
    page.wait_for_timeout(1000)

    # 15. 查看 evaluation via API
    evaluation = _api_get(page, f"/learning-plans/{plan_id}/evaluation", token)
    assert evaluation is not None, "evaluation response missing"

    # 16. 提交 feedback via API
    feedback = _api_post(page, f"/learning-plans/{plan_id}/feedback", token, {"feedback": "HELPFUL"})
    assert feedback is not None, "feedback response missing"

    # 17. 删除 MODEL_SHADOW_ONLY
    page.reload(wait_until="networkidle")
    page.wait_for_selector(".learning-state-page", timeout=10000)
    model_shadow_radio = page.query_selector("input[name='delete-scope'][value='MODEL_SHADOW_ONLY']")
    assert model_shadow_radio is not None, "MODEL_SHADOW_ONLY delete option not found"
    model_shadow_radio.click()
    page.wait_for_timeout(500)
    confirm_btn = page.query_selector(".ls-delete-confirm .ls-btn--danger")
    assert confirm_btn is not None, "delete confirm button not found"
    confirm_btn.click()
    page.wait_for_timeout(1000)

    # 18. 验证账号及其他状态仍存在
    page.reload(wait_until="networkidle")
    page.wait_for_selector(".learning-state-page", timeout=10000)
    assert page.query_selector(".ls-title") is not None, "page broken after deletion"

    # 19. 验证数据摘要仍可用
    summary = _api_get(page, "/learner-state/data-summary", token)
    assert summary is not None, "data summary missing after deletion"

    # 20. 预测世界模型页面、在线预测与反事实模拟必须真实可用
    page.goto(f"{BASE_URL}/prediction", wait_until="networkidle")
    page.wait_for_selector(".pred-page", timeout=15000)
    page.wait_for_selector(".pred-course-select select", timeout=15000)
    assert page.query_selector(".pred-error") is None, "prediction page rendered an API error"
    section_titles = [item.inner_text() for item in page.query_selector_all(".pred-section__title")]
    for expected in ("掌握度预测", "表现预测", "学习速度", "反事实模拟", "预测评测"):
        assert expected in section_titles, f"prediction section missing: {expected}"
    simulate_btn = page.query_selector(".pred-btn--primary:has-text('运行模拟')")
    assert simulate_btn is not None and simulate_btn.is_enabled(), "counterfactual simulation unavailable"
    simulate_btn.click()
    page.wait_for_function(
        "document.querySelector('.pred-sim-result') || document.querySelector('.pred-error')",
        timeout=30000,
    )
    error_bar = page.query_selector(".pred-error")
    assert error_bar is None, f"counterfactual simulation failed: {error_bar.inner_text() if error_bar else ''}"

    # 21. 最终无横向溢出
    _check_no_overflow(page, vp_name)


def main():
    print("Starting backend...")
    _start_backend()
    print(f"  backend ready at {BACKEND_URL}")

    print("Starting Vite...")
    _start_vite()
    print(f"  vite ready at {BASE_URL}")

    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for vp in VIEWPORTS:
            context = browser.new_context(
                viewport={"width": vp["width"], "height": vp["height"]},
                reduced_motion="reduce",
            )
            page = context.new_page()
            page_errors: list[str] = []
            page.on("pageerror", lambda e: page_errors.append(str(e)))
            try:
                token = _api_login(page, vp["username"], "Demo123456")
                run_closed_loop(page, vp, token)
                if page_errors:
                    raise AssertionError(f"page errors: {page_errors}")
                print(f"  PASS {vp['name']} ({vp['width']}x{vp['height']})")
            except Exception as e:
                failures.append((vp["name"], str(e)))
                print(f"  FAIL {vp['name']}: {e}", file=sys.stderr)
            finally:
                context.close()
        browser.close()

    print(f"E2E complete: {len(VIEWPORTS) - len(failures)}/{len(VIEWPORTS)} passed")
    if failures:
        print("\nFailed viewports:", file=sys.stderr)
        for name, err in failures:
            print(f"  - {name}: {err}", file=sys.stderr)
        _cleanup()
        sys.exit(1)

    _cleanup()


if __name__ == "__main__":
    main()
