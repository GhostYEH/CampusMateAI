"""通用学生世界模型的学习状态 E2E 闭环。

流程覆盖：登录、目标与进度、CORE/WORLD 状态证据、纠正与撤销、计划接受/执行/评估/反馈/撤销、
只读模拟、数据源暂停后的降级、恢复、透明度、影子数据删除和预测页面。
脚本使用独立后端数据库，失败时以非零状态退出，并在结束时关闭服务和清理临时数据。
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
        "Install with: pip install playwright && playwright install chromium\n"
        "or: npm install -D playwright && npx playwright install chromium",
        file=sys.stderr,
    )
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
WEBREACT_DIR = REPO_ROOT / "webreact"
BACKEND_PORT = int(os.environ.get("LEARNER_STATE_E2E_BACKEND_PORT", "8765"))
VITE_PORT = int(os.environ.get("LEARNER_STATE_E2E_VITE_PORT", "5174"))
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
    _tempdir = tempfile.mkdtemp(prefix="e2e_learner_state_")
    db_path = Path(_tempdir) / "e2e.db"
    env = os.environ.copy()
    env["APP_ENV"] = "test"
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["AUTO_SEED_DEMO_USERS"] = "true"
    env["JWT_SECRET_KEY"] = "e2e-test-secret-key-for-testing-only"
    env["PYTHONPATH"] = str(BACKEND_DIR)
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(BACKEND_PORT),
        ],
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
    response = page.request.post(
        f"{API_BASE}/auth/login", data={"username": username, "password": password}
    )
    assert response.status == 200, f"login failed: {response.status} {response.text()}"
    return response.json()["access_token"]


def _api_post(page, path: str, token: str, data: dict | None = None) -> dict:
    response = page.request.post(
        f"{API_BASE}{path}",
        data=data or {},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status < 400, f"POST {path} failed: {response.status} {response.text()}"
    return response.json() if response.text() else {}


def _api_get(page, path: str, token: str) -> dict:
    response = page.request.get(
        f"{API_BASE}{path}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status < 400, f"GET {path} failed: {response.status} {response.text()}"
    return response.json()


def _seed_learner_data(page, token: str) -> None:
    """写入可投影的通用学习会话记录。"""
    for i in range(3):
        response = page.request.post(
            f"{API_BASE}/study/sessions",
            data={"goal": f"完成第{i + 1}次学习记录", "duration_minutes": 30 + i * 10},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status < 400, f"seed session failed: {response.status} {response.text()}"
        session = response.json()
        session_id = session.get("session_id") or session.get("id")
        assert session_id, f"seed session missing id: {session}"
        response = page.request.post(
            f"{API_BASE}/study/sessions/{session_id}/finish",
            data={"self_report": "完成了本次学习记录", "duration_minutes": 30 + i * 10},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status < 400, f"finish session failed: {response.status} {response.text()}"


def _assert_page(body: dict, label: str) -> None:
    for field in ("items", "total", "page", "page_size", "has_more"):
        assert field in body, f"{label} page missing {field}: {body}"
    assert isinstance(body["items"], list), f"{label} items must be a list"


def _assert_evidence(body: dict, label: str, require_items: bool) -> None:
    _assert_page(body, label)
    if require_items:
        assert body["items"], f"{label} evidence empty"
    for item in body["items"]:
        for field in ("evidence_kind", "source_category", "role", "explanation_code"):
            assert item.get(field), f"{label} evidence missing safe field {field}: {item}"
        for forbidden in ("source_id", "table_name", "payload", "prompt", "source_text", "answer"):
            assert forbidden not in item, f"{label} evidence leaks {forbidden}: {item}"


def _check_no_overflow(page, viewport_name: str) -> None:
    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    client_width = page.evaluate("document.documentElement.clientWidth")
    assert scroll_width <= client_width + 1, (
        f"horizontal overflow at {viewport_name}: {scroll_width} > {client_width}"
    )


def _wait_for_learning_state(page) -> None:
    page.wait_for_selector(".learning-state-page", timeout=15000)
    title = page.locator(".ls-title")
    assert title.count() == 1 and (title.text_content() or "").strip(), "title element is empty"


def _summary_counts(summary: dict) -> tuple[int, ...]:
    return tuple(
        int(summary.get(key, 0))
        for key in (
            "event_count",
            "snapshot_count",
            "correction_count",
            "learning_plan_count",
            "plan_feedback_count",
            "plan_evaluation_count",
            "shadow_run_count",
        )
    )


def run_closed_loop(page, viewport, token: str) -> None:
    vp_name = viewport["name"]
    page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})

    # 1. 登录并进入当前用户空间
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

    # 2. 打开学习状态页并确认布局
    page.goto(f"{BASE_URL}/learning-state", wait_until="networkidle")
    _wait_for_learning_state(page)
    _check_no_overflow(page, vp_name)

    # 3. 写入通用学习记录
    _seed_learner_data(page, token)

    # 4. 创建通用个人成长目标
    goal_result = _api_post(
        page,
        "/student-goals",
        token,
        {
            "name": "完成世界模型闭环验证",
            "category": "personal_growth",
            "target_date": "2099-12-31",
            "initial_progress_percent": 10,
            "milestone_count": 2,
            "idempotency_key": f"e2e-goal-{viewport['username']}",
        },
    )
    goal = goal_result.get("goal", {})
    goal_id = goal.get("goal_id")
    assert goal_id and goal.get("status") == "active", f"goal create failed: {goal_result}"

    # 5. 更新目标进度
    progress_result = _api_post(
        page,
        f"/student-goals/{goal_id}/progress",
        token,
        {
            "progress_percent": 35,
            "milestone_reached": "完成接口检查",
            "idempotency_key": f"e2e-progress-{viewport['username']}",
        },
    )
    assert progress_result.get("goal", {}).get("progress_percent") == 35, (
        f"goal progress update failed: {progress_result}"
    )

    # 6. 读取 CORE 状态与安全证据
    page.reload(wait_until="networkidle")
    _wait_for_learning_state(page)
    core_page = _api_get(page, "/learner-state/snapshots?scope_type=USER&page=1&page_size=50", token)
    _assert_page(core_page, "CORE snapshots")
    assert core_page["items"], f"no CORE snapshots: {core_page}"
    core_snapshot = core_page["items"][0]
    core_snapshot_id = core_snapshot.get("snapshot_id")
    assert core_snapshot_id, f"CORE snapshot missing id: {core_snapshot}"
    core_evidence = _api_get(
        page, f"/learner-state/snapshots/{core_snapshot_id}/evidence?page=1&page_size=20", token
    )
    _assert_evidence(core_evidence, "CORE", True)
    page.locator(".ls-state-card .ls-link-btn").first.click()
    page.wait_for_selector(".ls-drawer", timeout=5000)

    # 7. 读取 WORLD 投影与安全证据
    world_page = _api_get(
        page,
        "/learner-state/snapshots?projection_kind=WORLD&projection_scope=__user__&page=1&page_size=50",
        token,
    )
    _assert_page(world_page, "WORLD snapshots")
    assert world_page["items"], f"no WORLD snapshots: {world_page}"
    assert all(item.get("projection_kind") == "WORLD" for item in world_page["items"])
    world_snapshot = world_page["items"][0]
    world_evidence = _api_get(
        page, f"/learner-state/snapshots/{world_snapshot['snapshot_id']}/evidence?page=1&page_size=20", token
    )
    _assert_evidence(world_evidence, "WORLD", False)

    # 8. 提交状态纠正
    correction_options = page.locator(".ls-correction-options .ls-btn")
    assert correction_options.count() > 0, "no correction options in evidence drawer"
    correction_options.first.click()
    submit_correction = page.locator(".ls-drawer__correction .ls-btn--primary")
    assert submit_correction.count() == 1 and submit_correction.is_enabled(), "correction submit unavailable"
    submit_correction.click()
    page.wait_for_selector(".ls-correction-msg", timeout=5000)

    # 9. 撤销状态纠正
    page.locator(".ls-drawer__close").click()
    page.reload(wait_until="networkidle")
    _wait_for_learning_state(page)
    corrections = _api_get(page, "/learner-state/corrections?page=1&page_size=20", token)
    assert corrections.get("items"), f"no correction record: {corrections}"
    correction_id = corrections["items"][0]["correction_id"]
    revoked = _api_post(
        page,
        f"/learner-state/corrections/{correction_id}/revoke",
        token,
        {"idempotency_key": f"e2e-revoke-{viewport['username']}"},
    )
    assert revoked.get("status") == "REVOKED", f"correction revoke failed: {revoked}"

    # 10. 生成通用行动计划
    plan = _api_post(
        page,
        "/learning-plans/generate",
        token,
        {"available_minutes": 60, "idempotency_key": f"e2e-plan-{viewport['username']}"},
    )
    plan_id = plan.get("plan_id")
    assert plan_id and plan.get("status") == "PROPOSED", f"plan generate failed: {plan}"

    # 11. 接受计划
    accepted = _api_post(page, f"/learning-plans/{plan_id}/decision", token, {"decision": "ACCEPT"})
    assert accepted.get("status") == "ACCEPTED", f"plan accept failed: {accepted}"

    # 12. 执行计划
    executed = _api_post(page, f"/learning-plans/{plan_id}/execute", token)
    assert executed.get("status") in {"EXECUTED", "PARTIALLY_EXECUTED"}, (
        f"plan execute failed: {executed}"
    )

    # 13. 查看计划评估
    evaluation = _api_get(page, f"/learning-plans/{plan_id}/evaluation", token)
    assert evaluation.get("plan_id") == plan_id, f"evaluation missing: {evaluation}"

    # 14. 提交计划反馈
    feedback = _api_post(page, f"/learning-plans/{plan_id}/feedback", token, {"feedback": "HELPFUL"})
    assert feedback.get("plan_id") == plan_id, f"feedback failed: {feedback}"

    # 15. 撤销已执行计划
    undone = _api_post(page, f"/learning-plans/{plan_id}/undo", token)
    assert undone.get("status") == "UNDONE", f"plan undo failed: {undone}"

    # 16. 运行只读模拟并确认业务计数不变
    summary_before_sim = _api_get(page, "/learner-state/data-summary", token)
    simulation = _api_post(
        page,
        "/learner-state/simulations",
        token,
        {
            "baseline_run_id": world_snapshot["run_id"],
            "intervention": {
                "intervention_type": "REDUCE_DAILY_LOAD",
                "reduce_minutes_per_day": 30,
                "movable_task_policy": "PERSONAL_ONLY",
            },
            "horizon_days": 7,
            "idempotency_key": f"e2e-simulation-{viewport['username']}",
        },
    )
    assert simulation.get("simulation_id"), f"simulation missing id: {simulation}"
    assert "intervention_not_executed" in simulation.get("limitations", []), (
        f"simulation is missing read-only limitation: {simulation}"
    )
    summary_after_sim = _api_get(page, "/learner-state/data-summary", token)
    assert _summary_counts(summary_after_sim) == _summary_counts(summary_before_sim), (
        "simulation changed learner business counts"
    )

    # 17. 暂停通用数据源、确认 WORLD 降级，再恢复并查看透明度
    page.reload(wait_until="networkidle")
    _wait_for_learning_state(page)
    source_rows = page.locator(".ls-source-row")
    assert source_rows.count() == 6, f"unexpected generic source count: {source_rows.count()}"
    chaoxing_row = source_rows.nth(2)
    chaoxing_row.get_by_role("button", name="暂停").click()
    page.wait_for_timeout(700)
    paused_controls = _api_get(page, "/learner-state/data-controls", token)
    paused = {item["source_key"]: item["status"] for item in paused_controls["items"]}
    assert paused.get("CHAOXING") == "PAUSED", f"source pause failed: {paused_controls}"
    degraded_world = _api_get(
        page,
        "/learner-state/snapshots?projection_kind=WORLD&projection_scope=__user__&page=1&page_size=50",
        token,
    )
    assert any("learner_data_source_paused" in item.get("warning_codes", []) for item in degraded_world["items"]), (
        f"WORLD projection did not expose paused-source degradation: {degraded_world}"
    )
    page.reload(wait_until="networkidle")
    _wait_for_learning_state(page)
    page.locator(".ls-source-row").nth(2).get_by_role("button", name="恢复").click()
    page.wait_for_timeout(700)
    resumed_controls = _api_get(page, "/learner-state/data-controls", token)
    resumed = {item["source_key"]: item["status"] for item in resumed_controls["items"]}
    assert resumed.get("CHAOXING") == "ENABLED", f"source resume failed: {resumed_controls}"
    transparency = _api_get(page, "/learner-state/model-transparency", token)
    assert isinstance(transparency.get("capabilities"), list), f"transparency missing capabilities: {transparency}"
    assert page.locator(".ls-transparency").count() == 1, "transparency section is not rendered"

    # 18. 删除模型影子数据、验证连续性并检查在线预测与模拟页面
    summary_before_delete = _api_get(page, "/learner-state/data-summary", token)
    shadow_option = page.locator("input[name='delete-scope'][value='MODEL_SHADOW_ONLY']")
    assert shadow_option.count() == 1, "MODEL_SHADOW_ONLY delete option not found"
    shadow_option.check()
    confirm_delete = page.locator(".ls-delete-confirm .ls-btn--danger")
    assert confirm_delete.count() == 1, "delete confirm button not found"
    confirm_delete.click()
    page.wait_for_timeout(700)
    page.reload(wait_until="networkidle")
    _wait_for_learning_state(page)
    summary_after_delete = _api_get(page, "/learner-state/data-summary", token)
    assert summary_after_delete["event_count"] == summary_before_delete["event_count"]
    assert summary_after_delete["learning_plan_count"] == summary_before_delete["learning_plan_count"]

    page.goto(f"{BASE_URL}/prediction", wait_until="networkidle")
    page.wait_for_selector(".pred-page", timeout=15000)
    assert page.locator(".pred-horizon-select").count() == 1, "prediction horizon control is missing"
    assert page.locator(".pred-error").count() == 0, "prediction page rendered an API error"
    section_titles = page.locator(".pred-section__title").all_text_contents()
    for expected in ("未来负载", "截止风险", "日程冲突", "目标进展", "方案 A/B 对比"):
        assert expected in section_titles, f"prediction section missing: {expected}"
    simulate_button = page.locator(".pred-btn--primary").filter(has_text="运行模拟")
    assert simulate_button.count() == 1 and simulate_button.is_enabled(), "counterfactual simulation unavailable"
    simulate_button.click()
    page.wait_for_function(
        "document.querySelector('.pred-sim-result') || document.querySelector('.pred-error')",
        timeout=30000,
    )
    assert page.locator(".pred-error").count() == 0, "counterfactual simulation failed"
    _check_no_overflow(page, vp_name)


def main() -> None:
    print("Starting backend...")
    _start_backend()
    print(f"  backend ready at {BACKEND_URL}")
    print("Starting Vite...")
    _start_vite()
    print(f"  vite ready at {BASE_URL}")

    failures = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for viewport in VIEWPORTS:
            context = browser.new_context(
                viewport={"width": viewport["width"], "height": viewport["height"]},
                reduced_motion="reduce",
            )
            page = context.new_page()
            page_errors: list[str] = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            try:
                token = _api_login(page, viewport["username"], "Demo123456")
                run_closed_loop(page, viewport, token)
                if page_errors:
                    raise AssertionError(f"page errors: {page_errors}")
                print(f"  PASS {viewport['name']} ({viewport['width']}x{viewport['height']})")
            except Exception as exc:
                failures.append((viewport["name"], str(exc)))
                print(f"  FAIL {viewport['name']}: {exc}", file=sys.stderr)
            finally:
                context.close()
        browser.close()

    print(f"E2E complete: {len(VIEWPORTS) - len(failures)}/{len(VIEWPORTS)} passed")
    if failures:
        print("\nFailed viewports:", file=sys.stderr)
        for name, error in failures:
            print(f"  - {name}: {error}", file=sys.stderr)
        _cleanup()
        sys.exit(1)
    _cleanup()


if __name__ == "__main__":
    main()
