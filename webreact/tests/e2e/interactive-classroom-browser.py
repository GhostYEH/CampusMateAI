"""互动课堂课程详情的浏览器级黄金路径。

使用 Playwright 真浏览器点击课程详情页：页面 API 用 route mock 隔离，
因此该测试验证的是 React 页面、表单交互、轮询和内容回读，而不是测试后端实现。
"""
from __future__ import annotations

import json
import os
import re
from urllib.parse import urlparse

from playwright.sync_api import Page, Route, expect, sync_playwright


BASE = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5184")
COURSE_ID = "course-browser"
SESSION_ID = "session-browser"
EMBED_URL = "https://classroom.example.com/classroom/session-browser"


def _json(route: Route, value: object, status: int = 200) -> None:
    route.fulfill(
        status=status,
        content_type="application/json",
        body=json.dumps(value, ensure_ascii=False),
    )


def install_api_mock(
    page: Page,
    classroom_url: str = EMBED_URL,
    embed_origin: str = "https://classroom.example.com",
    history_items: list[dict] | None = None,
    cpm: bool = False,
) -> list[dict]:
    requests: list[dict] = []
    job_polls: dict[str, int] = {}
    cpm_job_polls = {"count": 0}

    def handle(route: Route) -> None:
        request = route.request
        parsed = urlparse(request.url)
        path = parsed.path
        method = request.method
        requests.append({"method": method, "path": path, "post_data": request.post_data})

        if path.endswith("/health"):
            _json(route, {"ok": True})
        elif path.endswith("/dashboard/student"):
            _json(route, {})
        elif path.endswith("/agenda/today"):
            _json(route, {"summary": {"pending": 0}, "items": []})
        elif cpm and path.endswith("/counselor/chat") and method == "POST":
            route.fulfill(
                status=200,
                headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache"},
                body=(
                    'event: chunk\ndata: {"text":"我建议先确认一节互动课堂"}\n\n'
                    'event: done\ndata: {"answer":"我建议先确认一节互动课堂","conversation_id":"conv-browser",'
                    '"suggested_actions":[{"id":"classroom-browser","label":"生成互动课堂",'
                    '"type":"interactiveClassroomProposal","data":{"course_id":"course-browser",'
                    '"course_name":"高等数学","mode":"review","mode_label":"考前复习",'
                    '"intent_note":"内容形态只是生成意图，最终包含哪些形式由生成器根据课程内容决定。",'
                    '"available":true,"requires_confirmation":true}}]}\n\n'
                ),
            )
        elif cpm and path == "/api/v1/agent-jobs" and method == "POST":
            _json(route, {
                "job_id": "job-browser",
                "job_kind": "interactive_classroom",
                "status": "QUEUED",
                "latest_run_id": "run-browser",
                "input_ref": {"course_id": COURSE_ID, "mode": "review"},
            }, status=202)
        elif cpm and path.endswith("/agent-jobs/job-browser") and method == "GET":
            cpm_job_polls["count"] += 1
            if cpm_job_polls["count"] == 1:
                _json(route, {
                    "job_id": "job-browser",
                    "job_kind": "interactive_classroom",
                    "status": "AWAITING_APPROVAL",
                    "latest_run_id": "run-browser",
                    "pending_approval_id": "approval-browser",
                    "input_ref": {"course_id": COURSE_ID, "mode": "review"},
                })
            else:
                _json(route, {
                    "job_id": "job-browser",
                    "job_kind": "interactive_classroom",
                    "status": "SUCCEEDED",
                    "latest_run_id": "run-browser",
                    "input_ref": {
                        "course_id": COURSE_ID,
                        "mode": "review",
                        "session_id": SESSION_ID,
                        "deep_link": f"/courses/{COURSE_ID}?tab=mentoring&session={SESSION_ID}",
                    },
                })
        elif cpm and path.endswith("/agent-approvals/approval-browser/decision") and method == "POST":
            _json(route, {
                "approval_id": "approval-browser",
                "run_id": "run-browser",
                "status": "APPROVED",
            })
        elif path == f"/api/v1/courses/{COURSE_ID}" and method == "GET":
            _json(route, {
                "id": COURSE_ID,
                "name": "高等数学",
                "code": "MATH-101",
                "description": "浏览器闭环测试课程",
                "teacher_name": "测试教师",
                "semester": "2026 春",
            })
        elif path == f"/api/v1/classes" and method == "GET":
            _json(route, {"items": []})
        elif path.endswith(f"/courses/{COURSE_ID}/content-summary"):
            _json(route, {})
        elif path.endswith(f"/courses/{COURSE_ID}/content"):
            _json(route, {"items": []})
        elif path.endswith(f"/courses/{COURSE_ID}/knowledge-graph"):
            _json(route, {"available": False})
        elif path.endswith(f"/courses/{COURSE_ID}/interactive-classroom/status"):
            _json(route, {
                "enabled": True,
                "configured": True,
                "available": True,
                "browser_embed_available": True,
                "embed_origin": embed_origin,
                "service": "magicclass",
                "version": "0.1.0",
                "poll_interval_ms": 1,
                "external_3d_available": True,
            })
        elif path.endswith(f"/courses/{COURSE_ID}/interactive-classroom/plan"):
            _json(route, {
                "course_id": COURSE_ID,
                "course_name": "高等数学",
                "mode": "adaptive",
                "mode_label": "自动推荐",
                "adaptive_reason": "根据近期错题优先补强薄弱点",
                "materials": [{"id": "mat-1", "title": "第三章讲义", "kind": "document"}],
                "context_warnings": [],
                "can_generate": True,
                "external_3d_available": True,
            })
        elif path == f"/api/v1/courses/{COURSE_ID}/interactive-classroom" and method == "GET":
            _json(route, {"enabled": True, "items": history_items or []})
        elif path.endswith(f"/courses/{COURSE_ID}/interactive-classroom/generate") and method == "POST":
            generation_count = sum(
                1
                for item in requests
                if item["method"] == "POST" and item["path"].endswith("/interactive-classroom/generate")
            )
            session_id = SESSION_ID if generation_count == 1 else "session-browser-failed"
            _json(route, {
                "session": {
                    "session_id": session_id,
                    "course_id": COURSE_ID,
                    "mode": "adaptive",
                    "status": "queued",
                    "step": "queued",
                    "progress": 5,
                    "message": "已排队",
                    "terminal": False,
                    "retryable": False,
                },
                "poll_interval_ms": 300,
            }, status=202)
        elif re.search(rf"/courses/{COURSE_ID}/interactive-classroom/session-browser-failed/retry$", path) and method == "POST":
            _json(route, {
                "session": {
                    "session_id": "session-browser-retry",
                    "course_id": COURSE_ID,
                    "mode": "adaptive",
                    "status": "queued",
                    "step": "queued",
                    "progress": 5,
                    "message": "已重新排队",
                    "terminal": False,
                    "retryable": False,
                },
                "poll_interval_ms": 300,
            }, status=202)
        elif re.search(r"/interactive-classroom/jobs/([^/]+)$", path):
            session_id = path.rsplit("/", 1)[-1]
            job_polls[session_id] = job_polls.get(session_id, 0) + 1
            if session_id == "session-browser-failed":
                _json(route, {
                    "session_id": session_id,
                    "course_id": COURSE_ID,
                    "mode": "adaptive",
                    "status": "failed",
                    "step": "failed",
                    "progress": 42,
                    "message": "课堂生成失败",
                    "error": "模拟上游超时",
                    "error_code": "MAGICCLASS_GENERATION_FAILED",
                    "terminal": True,
                    "retryable": True,
                })
            elif job_polls[session_id] == 1:
                _json(route, {
                    "session_id": session_id,
                    "course_id": COURSE_ID,
                    "mode": "adaptive",
                    "status": "running",
                    "step": "generating_scenes",
                    "progress": 42,
                    "message": "正在生成课堂场景",
                    "terminal": False,
                    "retryable": False,
                })
            else:
                _json(route, {
                    "session_id": session_id,
                    "course_id": COURSE_ID,
                    "mode": "adaptive",
                    "status": "succeeded",
                    "step": "completed",
                    "progress": 100,
                    "message": "课堂已生成",
                    "url": classroom_url,
                    "scenes_count": 2,
                    "terminal": True,
                    "retryable": False,
                })
        elif re.search(r"/interactive-classroom/(session-browser|session-browser-retry)/composition$", path):
            _json(route, {
                "session_id": SESSION_ID,
                "scene_total": 2,
                "scenes": [{"type": "slide", "count": 1}, {"type": "quiz", "count": 1}],
                "widget_types": [{"widget_type": "diagram", "count": 1}],
                "has_whiteboard": True,
                "has_tts": False,
                "has_multi_agent": False,
                "requires_external_3d": False,
                "external_3d_available": True,
            })
        else:
            _json(route, {})

    page.route("**/api/v1/**", handle)
    return requests


def seed_student_session(page: Page) -> None:
    page.add_init_script(
        """
        localStorage.setItem('campus_access_token', 'browser-test-token');
        localStorage.setItem('campus_session', JSON.stringify({
          id: 'student-browser', username: 'student_browser', name: '测试学生', role: 'student'
        }));
        """
    )


def install_multi_proposal_mock(page: Page) -> list[dict]:
    """连续两个提案（第二个还跨课程）的 API mock。

    第一个提案故意**停在 QUEUED 不完成**，用来复现真实故障：
    修复前第二个提案会复用第一个提案的 reducer / job / 深链，
    学生点"确认生成"要么什么都不发生，要么直接看到上一节课的链接。
    """
    requests: list[dict] = []
    chat_count = {"n": 0}

    proposals = [
        {
            "proposal_id": "icp-first",
            "course_id": "course-browser",
            "course_name": "高等数学",
            "mode": "review",
            "mode_label": "考前复习",
        },
        {
            "proposal_id": "icp-second",
            "course_id": "course-browser-2",
            "course_name": "线性代数",
            "mode": "quiz",
            "mode_label": "练习测验",
        },
    ]
    jobs = {"icp-first": "job-first", "icp-second": "job-second"}

    def handle(route: Route) -> None:
        request = route.request
        parsed = urlparse(request.url)
        path = parsed.path
        method = request.method
        requests.append({"method": method, "path": path, "post_data": request.post_data})

        if path.endswith("/health"):
            _json(route, {"ok": True})
        elif path.endswith("/dashboard/student"):
            _json(route, {})
        elif path.endswith("/agenda/today"):
            _json(route, {"summary": {"pending": 0}, "items": []})
        elif path.endswith("/counselor/chat") and method == "POST":
            index = min(chat_count["n"], len(proposals) - 1)
            chat_count["n"] += 1
            proposal = proposals[index]
            payload = json.dumps(
                {
                    "id": "interactive-classroom",
                    "label": f"生成一节「{proposal['mode_label']}」互动课堂",
                    "type": "interactiveClassroomProposal",
                    "data": {
                        **proposal,
                        "intent_note": "内容形态只是生成意图，最终包含哪些形式由生成器根据课程内容决定。",
                        "available": True,
                        "requires_confirmation": True,
                        "job_kind": "interactive_classroom",
                    },
                },
                ensure_ascii=False,
            )
            route.fulfill(
                status=200,
                headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache"},
                body=(
                    f'event: chunk\ndata: {{"text":"提案 {index + 1}"}}\n\n'
                    f'event: done\ndata: {{"answer":"提案 {index + 1}","conversation_id":"conv-multi-{index}",'
                    f'"suggested_actions":[{payload}]}}\n\n'
                ),
            )
        elif path == "/api/v1/agent-jobs" and method == "POST":
            body = json.loads(request.post_data or "{}")
            course_id = (body.get("input_ref") or {}).get("course_id")
            job_id = "job-second" if course_id == "course-browser-2" else "job-first"
            _json(route, {
                "job_id": job_id,
                "job_kind": "interactive_classroom",
                "status": "QUEUED",
                "latest_run_id": f"run-{job_id}",
                "input_ref": {"course_id": course_id, "mode": "review"},
            }, status=202)
        elif re.search(r"/agent-jobs/(job-first|job-second)$", path) and method == "GET":
            job_id = path.rsplit("/", 1)[-1]
            _json(route, {
                "job_id": job_id,
                "job_kind": "interactive_classroom",
                "status": "QUEUED",
                "latest_run_id": f"run-{job_id}",
                "input_ref": {},
            })
        elif path == f"/api/v1/courses/{COURSE_ID}" and method == "GET":
            _json(route, {"id": COURSE_ID, "name": "高等数学", "code": "MATH-101"})
        else:
            _json(route, {})

    page.route("**/api/v1/**", handle)
    return requests


def run_multi_proposal_case(browser) -> None:
    """连续两个提案 / 跨课程：第二个提案绝不能复用第一个的 job 与深链。"""
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    seed_student_session(page)
    requests = install_multi_proposal_mock(page)
    page.goto(
        f"{BASE}/counselor?course={COURSE_ID}&prompt=generate%20classroom",
        wait_until="networkidle",
    )

    card = page.get_by_role("region", name="互动课堂建议")
    expect(card).to_be_visible(timeout=10000)
    expect(card.get_by_text("高等数学", exact=False)).to_be_visible()

    # 第一个提案：确认后停在 QUEUED（故意不完成）
    card.get_by_role("button", name="确认生成", exact=True).click()
    expect(card.get_by_text("已排队，正在准备这节课")).to_be_visible(timeout=5000)

    # 第二个提案（跨课程）
    page.get_by_label("发送给 AI 的消息").fill("再给我来一节线性代数练习")
    page.get_by_role("button", name=re.compile("^发送$")).click()

    expect(card.get_by_text("线性代数", exact=False)).to_be_visible(timeout=10000)
    # 新提案必须是干净的：不能显示第一个提案的深链 / 审批 / 排队状态
    expect(card.get_by_text("去课程详情查看")).to_have_count(0)
    expect(card.get_by_text("已排队，正在准备这节课")).to_have_count(0)
    expect(card.get_by_role("button", name="批准并开始生成")).to_have_count(0)
    expect(card.get_by_role("button", name="确认生成", exact=True)).to_be_enabled()

    card.get_by_role("button", name="确认生成", exact=True).click()
    expect(card.get_by_text("已排队，正在准备这节课")).to_be_visible(timeout=5000)

    creates = [
        item for item in requests
        if item["method"] == "POST" and item["path"] == "/api/v1/agent-jobs"
    ]
    if len(creates) != 2:
        raise AssertionError(f"expected exactly one job per proposal, got {len(creates)}")
    second_payload = json.loads(creates[1]["post_data"] or "{}")
    if (second_payload.get("input_ref") or {}).get("course_id") != "course-browser-2":
        raise AssertionError(f"second proposal must target its own course: {second_payload}")

    def job_polls() -> list[str]:
        return [
            item["path"].rsplit("/", 1)[-1]
            for item in requests
            if item["method"] == "GET" and "/agent-jobs/" in item["path"]
        ]

    # 注意：这里必须用 page.wait_for_timeout 而不是 time.sleep ——
    # 同步 API 的 route handler 跑在 Playwright 的事件循环上，阻塞主线程会让
    # 新请求根本得不到派发，从而把一个真实存在的轮询误判成"没有轮询"。
    for _ in range(60):
        if "job-second" in job_polls():
            break
        page.wait_for_timeout(250)

    polls = job_polls()
    if "job-second" not in polls:
        raise AssertionError(
            f"second proposal must poll its own job: {polls}\nall requests: {requests}"
        )
    # 第一个提案的轮询在切到新提案时**应当**被停掉，所以 job-first 可能压根没被轮询过；
    # 只有它确实出现过时才比较先后（否则这条断言会变成时序竞态）。
    if "job-first" in polls and polls.index("job-second") < polls.index("job-first"):
        raise AssertionError(f"unexpected poll order: {polls}")

    # 第一个提案的深链绝不能出现在第二个提案上
    if page.get_by_text("去课程详情查看").count() != 0:
        raise AssertionError("第二个提案显示了旧提案的深链入口")

    print("PASS two consecutive proposals (cross-course) stay isolated")
    page.close()


def main() -> int:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        seed_student_session(page)
        requests = install_api_mock(page)
        page.goto(f"{BASE}/courses/{COURSE_ID}", wait_until="networkidle")
        expect(page.locator("h1", has_text="高等数学")).to_be_visible()

        page.get_by_role("button", name="智能辅导", exact=True).click()
        expect(page.get_by_role("heading", name="智能辅导")).to_be_visible()
        expect(page.get_by_role("radiogroup", name="选择辅导模式")).to_be_visible()
        expect(page.get_by_role("radiogroup", name="选择辅导模式").get_by_role("button")).to_have_count(9)

        page.get_by_label("学习目标").fill("期中考试前巩固第三章难点")
        page.get_by_label("第三章讲义").check()
        page.get_by_role("button", name=re.compile("确认生成")).click()

        expect(page.get_by_text("排队中").first).to_be_visible(timeout=1000)
        expect(page.get_by_text("生成课堂场景").first).to_be_visible(timeout=10000)
        expect(page.get_by_text("42%"), "running progress is visible").to_be_visible()
        expect(page.get_by_text("课堂已生成", exact=True).first).to_be_visible(timeout=10000)
        expect(page.get_by_text("已生成内容包含：幻灯片 ×1、测验 ×1")).to_be_visible(timeout=10000)
        classroom_frame = page.locator('iframe[title="智能辅导互动课堂"]')
        expect(classroom_frame).to_have_attribute("src", EMBED_URL)
        expect(classroom_frame).to_have_attribute("sandbox", "allow-scripts allow-same-origin allow-forms")
        expect(classroom_frame).to_have_attribute("referrerpolicy", "no-referrer")
        expect(page.get_by_role("button", name="在新窗口打开课堂")).to_be_enabled()

        page.get_by_role("button", name="重新生成", exact=True).click()
        page.get_by_role("button", name=re.compile("确认生成")).click()
        expect(page.get_by_text("模拟上游超时").first).to_be_visible(timeout=10000)
        expect(page.get_by_text("MAGICCLASS_GENERATION_FAILED")).to_be_visible()
        page.get_by_role("button", name="重新生成", exact=True).click()
        expect(page.get_by_text("课堂已生成", exact=True).first).to_be_visible(timeout=10000)

        retry_requests = [
            item for item in requests
            if item["method"] == "POST" and item["path"].endswith("/interactive-classroom/session-browser-failed/retry")
        ]
        if len(retry_requests) != 1:
            raise AssertionError(f"expected one retry request, got {len(retry_requests)}")

        generate_requests = [
            item for item in requests
            if item["method"] == "POST" and item["path"].endswith("/interactive-classroom/generate")
        ]
        if len(generate_requests) != 2:
            raise AssertionError(f"expected two explicit generate requests, got {len(generate_requests)}")
        payload = json.loads(generate_requests[0]["post_data"] or "{}")
        if payload.get("mode") != "adaptive" or payload.get("selected_material_ids") != ["mat-1"]:
            raise AssertionError(f"unexpected generation payload: {payload}")
        if payload.get("learning_objective") != "期中考试前巩固第三章难点":
            raise AssertionError(f"learning objective was not submitted: {payload}")

        print("PASS interactive classroom browser golden path")
        print(f"PASS generate request count={generated_count(requests)}")

        for label, origin, url in (
            ("same-origin", BASE, f"{BASE}/classroom/internal"),
            ("wrong-port", "http://127.0.0.1:5185", "http://127.0.0.1:5186/classroom/other-port"),
        ):
            blocked = browser.new_page(viewport={"width": 1440, "height": 1000})
            seed_student_session(blocked)
            install_api_mock(
                blocked,
                classroom_url=url,
                embed_origin=origin,
                history_items=[{"session_id": f"history-{label}", "mode": "review", "url": url}],
            )
            blocked.goto(f"{BASE}/courses/{COURSE_ID}", wait_until="networkidle")
            blocked.get_by_role("button", name="智能辅导", exact=True).click()
            expect(blocked.get_by_text("待打开")).to_be_visible(timeout=5000)
            expect(blocked.get_by_text("待打开")).to_be_disabled()
            expect(blocked.locator("iframe")).to_have_count(0)
            blocked.close()

        cpm_page = browser.new_page(viewport={"width": 1440, "height": 1000})
        seed_student_session(cpm_page)
        cpm_requests = install_api_mock(cpm_page, cpm=True)
        cpm_page.goto(f"{BASE}/counselor?course={COURSE_ID}&prompt=generate%20classroom", wait_until="networkidle")
        expect(cpm_page.get_by_role("region", name="互动课堂建议")).to_be_visible(timeout=10000)
        cpm_page.get_by_role("button", name="确认生成", exact=True).click()
        expect(cpm_page.get_by_text("已排队，正在准备这节课")).to_be_visible(timeout=5000)
        expect(cpm_page.get_by_role("button", name="批准并开始生成")).to_be_visible(timeout=10000)
        cpm_page.get_by_role("button", name="批准并开始生成").click()
        expect(cpm_page.get_by_text("课堂已生成").first).to_be_visible(timeout=10000)
        cpm_page.get_by_role("button", name="去课程详情查看").click()
        cpm_page.wait_for_url(re.compile(r"/courses/course-browser\?tab=mentoring&session=session-browser$"))
        cpm_job_creates = [
            item for item in cpm_requests
            if item["method"] == "POST" and item["path"] == "/api/v1/agent-jobs"
        ]
        cpm_approvals = [
            item for item in cpm_requests
            if item["method"] == "POST" and item["path"].endswith("/agent-approvals/approval-browser/decision")
        ]
        if len(cpm_job_creates) != 1 or len(cpm_approvals) != 1:
            raise AssertionError(
                f"expected one CPM job and one approval, got {len(cpm_job_creates)} / {len(cpm_approvals)}"
            )
        cpm_job_gets = [
            item for item in cpm_requests
            if item["method"] == "GET" and item["path"].endswith("/agent-jobs/job-browser")
        ]
        if len(cpm_job_gets) < 2:
            raise AssertionError(f"expected same CPM job to be polled before and after approval: {cpm_job_gets}")
        print("PASS CPM queued -> awaiting approval -> approved -> succeeded on the same job")
        cpm_page.close()

        run_multi_proposal_case(browser)
        browser.close()
    return 0


def generated_count(requests: list[dict]) -> int:
    return sum(
        1 for item in requests
        if item["method"] == "POST" and item["path"].endswith("/interactive-classroom/generate")
    )


if __name__ == "__main__":
    raise SystemExit(main())
