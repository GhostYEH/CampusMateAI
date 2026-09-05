import json
import os

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5174")


def fixture(route):
    path = route.request.url.split("?")[0]
    if path.endswith("/courses"):
        return {"items": [{"id": "course-1", "name": "数据结构", "code": "CS101", "semester": "2026 秋", "resource_count": 3, "updated_at": "2026-09-05"}]}
    if path.endswith("/student/assignments"):
        return {"items": [{"id": "assignment-1", "course_id": "course-1", "title": "实验报告", "submission_status": "submitted"}]}
    if path.endswith("/student/exams"):
        return {"items": [{"id": "exam-1", "course_name": "数据结构", "exam_date": "2099-12-31", "start_time": "09:00", "location": "A101"}]}
    if path.endswith("/study/sessions/active"):
        return None
    if path.endswith("/study/sessions"):
        return {"items": [{"id": "study-1", "goal": "复习", "status": "completed", "started_at": "2026-09-05T10:00:00", "duration_seconds": 1800}]}
    if path.endswith("/tasks"):
        return {"items": [{"id": "task-1", "title": "整理笔记", "status": "completed", "completed_at": "2026-09-05T11:00:00", "created_at": "2026-09-04T11:00:00"}]}
    if path.endswith("/universities"):
        return {"items": [{"id": "uni-1", "name": "示例大学", "short_name": "示大", "city": "北京", "forum_enabled": True}]}
    if path.endswith("/auth/me"):
        return {"id": "student-1", "username": "test", "university_id": "uni-0"}
    return {"items": []}


def run():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def fulfill(route):
            if "/auth/trusted-device/" in route.request.url or route.request.url.split("?")[0].endswith("/health"):
                route.fulfill(status=404, content_type="application/json", body='{"detail":"not available in fixture"}')
                return
            route.fulfill(status=200, content_type="application/json", body=json.dumps(fixture(route), ensure_ascii=False))

        page.route("**/api/**", fulfill)
        page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        page.wait_for_selector(".login-panel-head h2", timeout=10000)
        page.evaluate("""() => {
          localStorage.setItem('campus_access_token', 'smoke-token');
          localStorage.setItem('campus_session', JSON.stringify({role: 'student', name: '测试同学'}));
        }""")

        page.goto(f"{BASE_URL}/courses", wait_until="networkidle")
        assert page.get_by_text("待完成作业").is_visible()
        assert "100%" in page.locator("main").inner_text(), page.locator("main").inner_text()
        page.get_by_label("课程排序").select_option("updated")

        page.goto(f"{BASE_URL}/exams/exam-1", wait_until="networkidle")
        assert page.get_by_text("距离开考").is_visible()
        assert page.get_by_role("button", name="刷新").is_visible()

        page.goto(f"{BASE_URL}/study", wait_until="networkidle")
        assert page.get_by_text("专注趋势（本周）").is_visible()
        page.get_by_role("button", name="进入沉浸模式").click()
        assert page.get_by_role("dialog").is_visible()
        page.get_by_role("button", name="返回学习陪伴").click()

        page.goto(f"{BASE_URL}/tasks", wait_until="networkidle")
        assert page.get_by_text("近七日完成趋势").is_visible()

        page.goto(f"{BASE_URL}/university", wait_until="networkidle")
        dialog_messages = []
        page.once("dialog", lambda dialog: (dialog_messages.append(dialog.message), dialog.dismiss()))
        page.get_by_role("button", name="选择大学").click()
        assert dialog_messages and "个人待办不会删除" in dialog_messages[0]

        assert not errors, errors
        browser.close()


if __name__ == "__main__":
    run()
