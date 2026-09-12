"""Phase 7C.1: 学习状态旅程 E2E 强制闭环测试。

自动启动独立测试数据库后端和 Vite，执行完整强制闭环：
登录 → 打开学习状态 → 查看 CORE/KNOWLEDGE evidence → 提交并撤销纠正 →
暂停并恢复 PRACTICE → 生成、接受、执行计划 → 查看 evaluation →
提交 feedback → 删除 MODEL_SHADOW_ONLY → 验证账号及其他状态仍存在

覆盖桌面和移动端，无横向溢出、无 pageerror。
关键流程全部强制断言：不存在按钮或没有生成数据时必须失败，不能跳过。
缺少 Playwright 时直接非零退出，不能伪通过。
测试结束必须可靠关闭服务并清理临时数据库。
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
import urllib.request
import urllib.error
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
BACKEND_PORT = 8765
VITE_PORT = 5174
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
BASE_URL = f"http://127.0.0.1:{VITE_PORT}"
API_BASE = f"{BACKEND_URL}/api/v1"

VIEWPORTS = [
    {"width": 1440, "height": 900, "name": "desktop"},
    {"width": 390, "height": 844, "name": "mobile"},
]

_processes: list[subprocess.Popen] = []
_tempdir: str | None = None


def _process_output(proc: subprocess.Popen, limit: int = 4000) -> str:
    try:
        if proc.stdout is None:
            return ""
        import select

        output = ""
        while True:
            ready, _, _ = select.select([proc.stdout], [], [], 0.1)
            if not ready:
                break
            chunk = proc.stdout.read1(4096) if hasattr(proc.stdout, "read1") else proc.stdout.read(4096)
            if not chunk:
                break
            output += chunk.decode("utf-8", errors="replace") if isinstance(chunk, bytes) else chunk
            if len(output) >= limit:
                break
        return output[-limit:]
    except Exception:
        return ""


def _check_process_alive(proc: subprocess.Popen, name: str) -> None:
    if proc.poll() is not None:
        output = _process_output(proc)
        raise RuntimeError(f"{name} exited early with code {proc.returncode}. Output:\n{output}")


def _wait_for_port(port: int, proc: subprocess.Popen, name: str, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        _check_process_alive(proc, name)
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except (ConnectionRefusedError, OSError):
            time.sleep(0.3)
    _check_process_alive(proc, name)
    raise RuntimeError(f"port {port} not ready within {timeout}s")


def _wait_for_http(url: str, proc: subprocess.Popen, name: str, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        _check_process_alive(proc, name)
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status < 500:
                    return
        except (urllib.error.URLError, ConnectionRefusedError, OSError):
            time.sleep(0.3)
    _check_process_alive(proc, name)
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
    _wait_for_http(f"{BACKEND_URL}/", proc, "backend", timeout=60)


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
    _wait_for_port(VITE_PORT, proc, "vite", timeout=60)


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


def _api_login(request, username: str, password: str) -> tuple[str, dict]:
    resp = request.post(f"{API_BASE}/auth/login", data={"username": username, "password": password})
    assert resp.status == 200, f"login failed: {resp.status} {resp.text}"
    body = resp.json()
    assert body.get("access_token"), "login response missing access_token"
    me_resp = request.get(
        f"{API_BASE}/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me_resp.status == 200, f"auth/me failed: {me_resp.status} {me_resp.text}"
    me_body = me_resp.json()
    user = me_body.get("user") or me_body
    assert user.get("id"), f"auth/me missing user id: {me_body}"
    return body["access_token"], user


def _page_api_post(page, path: str, data: dict | None = None) -> dict:
    result = page.evaluate(
        """async ([p, d]) => {
          const r = await fetch(p, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: 'Bearer ' + localStorage.getItem('campus_access_token'),
            },
            body: JSON.stringify(d || {}),
          });
          const text = await r.text();
          return { status: r.status, text: text.slice(0, 2000) };
        }""",
        [f"/api/v1{path}", data or {}],
    )
    assert result["status"] < 400, f"POST {path} failed: {result['status']} {result['text']}"
    import json as jsonlib

    return jsonlib.loads(result["text"]) if result["text"] else {}


def _page_api_get(page, path: str):
    result = page.evaluate(
        """async ([p]) => {
          const r = await fetch(p, {
            headers: { Authorization: 'Bearer ' + localStorage.getItem('campus_access_token') },
          });
          const text = await r.text();
          return { status: r.status, text: text.slice(0, 2000) };
        }""",
        [f"/api/v1{path}"],
    )
    assert result["status"] < 400, f"GET {path} failed: {result['status']} {result['text']}"
    import json as jsonlib

    return jsonlib.loads(result["text"]) if result["text"] else None


def _seed_learner_data(page) -> None:
    """Seed study sessions and personal tasks so projections and plans have data. 强制成功。"""
    for i in range(2):
        _page_api_post(page, "/tasks", {"title": f"E2E 复习任务{i+1}", "source_name": "E2E 种子数据"})
    created = 0
    for i in range(3):
        session = _page_api_post(
            page, "/study/sessions", {"goal": f"复习数据结构第{i+1}章", "duration_minutes": 30 + i * 10}
        )
        session_id = session.get("session_id") or session.get("id")
        assert session_id, f"seed session missing id: {session}"
        _page_api_post(
            page,
            f"/study/sessions/{session_id}/finish",
            {"self_report": "完成了一些练习题", "duration_minutes": 30 + i * 10},
        )
        created += 1
    assert created == 3, f"expected 3 seeded sessions, got {created}"


def _check_no_overflow(page, viewport_name: str) -> None:
    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    client_width = page.evaluate("document.documentElement.clientWidth")
    assert scroll_width <= client_width + 1, f"horizontal overflow at {viewport_name}: {scroll_width} > {client_width}"


def _ui_token_and_user(page) -> tuple[str, dict]:
    token = page.evaluate("localStorage.getItem('campus_access_token')")
    raw_session = page.evaluate("localStorage.getItem('campus_session')")
    assert token, "UI login did not persist campus_access_token"
    assert raw_session, "UI login did not persist campus_session"
    import json as jsonlib

    user = jsonlib.loads(raw_session)
    assert user.get("id"), f"UI session missing user id: {raw_session[:200]}"
    return token, user


def run_closed_loop(page, viewport, token: str, user: dict) -> None:
    """执行完整闭环测试。任一断言失败抛异常，无任何跳过。"""
    vp_name = viewport["name"]
    page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})

    # 1. 登录（UI 真实流程，token 与页面同源同用户）
    page.goto(f"{BASE_URL}/login", wait_until="networkidle")
    page.wait_for_selector("input[autoComplete='username']", timeout=10000)
    page.fill("input[autoComplete='username']", "student_demo")
    page.fill("input[autoComplete='current-password']", "Demo123456")
    page.click("button.login-submit")
    page.wait_for_url(f"{BASE_URL}/home", timeout=15000)
    token, user = _ui_token_and_user(page)

    # 2. 打开学习状态页面
    page.goto(f"{BASE_URL}/learning-state", wait_until="networkidle")
    page.wait_for_selector(".learning-state-page", timeout=15000)

    # 3. 验证页面标题
    title = page.query_selector(".ls-title")
    assert title is not None, "title element not found"
    assert "学习状态" in title.inner_text(), f"unexpected title: {title.inner_text()}"

    # 4. 验证无横向溢出
    _check_no_overflow(page, vp_name)

    # 5. Seed learner data via API and refresh（强制成功）
    _seed_learner_data(page)
    page.reload(wait_until="networkidle")
    page.wait_for_selector(".learning-state-page", timeout=15000)

    # 6. 查看 CORE evidence — 第一个"查看依据"按钮必须存在
    page.wait_for_selector(".ls-state-card .ls-link-btn", timeout=15000)
    view_evidence_btns = page.query_selector_all(".ls-state-card .ls-link-btn")
    assert len(view_evidence_btns) > 0, "no CORE evidence buttons found"
    view_evidence_btns[0].click()
    page.wait_for_selector(".ls-drawer", timeout=10000)
    drawer = page.query_selector(".ls-drawer")
    assert drawer is not None, "evidence drawer did not open"

    # KNOWLEDGE evidence：页面必须有知识地图或明确的空状态（不是静默跳过）
    knowledge_section = page.query_selector(".ls-knowledge")
    knowledge_empty = page.query_selector(".ls-knowledge + .ls-empty, .ls-empty")
    assert knowledge_section is not None or knowledge_empty is not None, "knowledge section missing entirely"

    # 7. 提交纠正（抽屉内纠正选项必须存在）
    correction_opts = page.query_selector_all(".ls-correction-options .ls-btn")
    assert len(correction_opts) > 0, "no correction options in drawer"
    correction_opts[0].click()
    page.wait_for_selector(".ls-drawer__correction .ls-btn--primary", timeout=5000)
    submit_btn = page.query_selector(".ls-drawer__correction .ls-btn--primary")
    assert submit_btn is not None, "correction submit button missing"
    assert submit_btn.is_enabled(), "correction submit button disabled"
    submit_btn.click()
    page.wait_for_selector(".ls-correction-msg", timeout=10000)
    correction_msg = page.query_selector(".ls-correction-msg")
    assert correction_msg is not None, "correction result message missing"

    # 8. 撤销纠正（纠正记录行必须存在）
    page.reload(wait_until="networkidle")
    page.wait_for_selector(".learning-state-page", timeout=15000)
    page.wait_for_selector(".ls-correction-row .ls-btn", timeout=15000)
    revoke_btns = page.query_selector_all(".ls-correction-row .ls-btn")
    assert len(revoke_btns) > 0, "no correction rows to revoke"
    revoke_btns[0].click()
    page.wait_for_selector(".ls-toast", timeout=10000)

    # 关闭抽屉（如果还开着）
    close_btn = page.query_selector(".ls-drawer__close")
    if close_btn:
        close_btn.click()
        page.wait_for_timeout(500)

    # 9. 暂停 PRACTICE 数据源（PRACTICE 行与暂停按钮必须存在）
    page.reload(wait_until="networkidle")
    page.wait_for_selector(".learning-state-page", timeout=15000)
    page.wait_for_selector(".ls-source-row", timeout=15000)
    source_rows = page.query_selector_all(".ls-source-row")
    assert len(source_rows) > 0, "no source rows found"
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
    page.wait_for_selector(".ls-toast", timeout=10000)
    _check_no_overflow(page, vp_name)

    # 10. 恢复 PRACTICE（恢复按钮必须出现）
    page.wait_for_selector(".ls-source-row .ls-btn:has-text('恢复')", timeout=10000)
    resume_btn = practice_row.query_selector(".ls-btn:has-text('恢复')")
    assert resume_btn is not None, "PRACTICE resume button not found"
    resume_btn.click()
    page.wait_for_selector(".ls-toast", timeout=10000)

    # 11. 生成计划 via API（强制成功）
    plan = _page_api_post(page, "/learning-plans/generate", {"available_minutes": 60})
    assert plan.get("plan_id") or plan.get("id"), f"plan generate missing id: {plan}"
    plan_id = plan.get("plan_id") or plan.get("id")

    # 12. 刷新页面查看计划（接受按钮必须存在）
    page.reload(wait_until="networkidle")
    page.wait_for_selector(".learning-state-page", timeout=15000)
    _check_no_overflow(page, vp_name)
    page.wait_for_selector(".ls-plan .ls-btn--primary:has-text('接受计划')", timeout=15000)
    accept_btn = page.query_selector(".ls-plan .ls-btn--primary:has-text('接受计划')")
    assert accept_btn is not None, "accept plan button not found"
    accept_btn.click()
    page.wait_for_selector(".ls-toast", timeout=10000)

    # 13. 执行计划（执行按钮必须出现）
    page.reload(wait_until="networkidle")
    page.wait_for_selector(".learning-state-page", timeout=15000)
    page.wait_for_selector(".ls-plan .ls-btn--primary:has-text('创建个人学习任务')", timeout=15000)
    execute_btn = page.query_selector(".ls-plan .ls-btn--primary:has-text('创建个人学习任务')")
    assert execute_btn is not None, "execute plan button not found"
    execute_btn.click()
    page.wait_for_selector(".ls-toast", timeout=10000)

    # 14. 查看 evaluation via API（强制成功）
    evaluation = _page_api_get(page, f"/learning-plans/{plan_id}/evaluation")
    assert evaluation is not None, "evaluation response missing"

    # 15. 提交 feedback via API（强制成功）
    feedback = _page_api_post(page, f"/learning-plans/{plan_id}/feedback", {"feedback": "HELPFUL"})
    assert feedback is not None, "feedback response missing"

    # 16. 删除 MODEL_SHADOW_ONLY（选项与确认按钮必须存在）
    page.reload(wait_until="networkidle")
    page.wait_for_selector(".learning-state-page", timeout=15000)
    page.wait_for_selector("input[name='delete-scope'][value='MODEL_SHADOW_ONLY']", timeout=15000)
    model_shadow_radio = page.query_selector("input[name='delete-scope'][value='MODEL_SHADOW_ONLY']")
    assert model_shadow_radio is not None, "MODEL_SHADOW_ONLY delete option not found"
    model_shadow_radio.click()
    page.wait_for_selector(".ls-delete-confirm .ls-btn--danger", timeout=5000)
    confirm_btn = page.query_selector(".ls-delete-confirm .ls-btn--danger")
    assert confirm_btn is not None, "delete confirm button not found"
    confirm_btn.click()
    page.wait_for_selector(".ls-toast", timeout=10000)

    # 17. 验证账号及其他状态仍存在
    page.reload(wait_until="networkidle")
    page.wait_for_selector(".learning-state-page", timeout=15000)
    assert page.query_selector(".ls-title") is not None, "page broken after deletion"

    # 18. 验证数据摘要仍可用（强制成功）
    summary = _page_api_get(page, "/learner-state/data-summary")
    assert summary is not None, "data summary missing after deletion"

    # 19. 最终无横向溢出
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
                run_closed_loop(page, vp, "", {})
                assert not page_errors, f"page errors: {page_errors}"
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
