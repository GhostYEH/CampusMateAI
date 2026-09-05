import os
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5174")


def payload(route, value):
    import json

    route.fulfill(status=200, content_type="application/json", body=json.dumps(value, ensure_ascii=False))


def run():
    now = datetime.now().astimezone()
    soon = (now + timedelta(days=3)).isoformat()
    later = (now + timedelta(days=10)).isoformat()
    requests = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def handle(route):
            parsed = urlparse(route.request.url)
            path = parsed.path
            requests.append((path, parse_qs(parsed.query)))
            if path.endswith("/auth/trusted-device/auto-login") or path.endswith("/health"):
                route.fulfill(status=404, content_type="application/json", body='{"detail":"not available in fixture"}')
                return
            if path.endswith("/dashboard/student"):
                return payload(route, {"pending_assignment_count": 1, "pending_personal_task_count": 1, "unread_announcement_count": 0, "enrolled_course_count": 1})
            if path.endswith("/courses"):
                return payload(route, {"items": [{"id": "course-1", "name": "数据结构"}]})
            if path.endswith("/study/sessions") or path.endswith("/edu/schedule/items") or path.endswith("/student/exams"):
                return payload(route, {"items": []})
            if path.endswith("/student/assignments"):
                return payload(route, {"items": [
                    {"id": "submitted-assignment", "title": "已提交实验报告", "submission_status": "submitted", "course_name": "数据结构"},
                    {"id": "late-assignment", "title": "逾期作业", "submission_status": "late", "deadline": (now - timedelta(days=1)).isoformat(), "course_name": "操作系统"},
                    {"id": "resubmitted-assignment", "title": "重新提交作业", "submission_status": "resubmitted", "deadline": soon, "course_name": "计算机网络"},
                ]})
            if path.endswith("/tasks"):
                return payload(route, {"items": [
                    {"id": "completed-task", "title": "已完成复习", "status": "completed", "deadline": later},
                    {"id": "upcoming-task", "title": "未来安排", "status": "pending", "deadline": soon},
                ]})
            if path.endswith("/notices"):
                return payload(route, {"items": [{"id": "read-notice", "title": "已读通知", "content": "材料已归档", "has_read": True}]})
            if path.endswith("/community/posts"):
                return payload(route, {"items": []})
            return payload(route, {"items": []})

        page.route("**/api/**", handle)
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
        page.wait_for_selector(".login-panel-head h2", timeout=10000)
        page.evaluate("""() => {
          localStorage.setItem('campus_access_token', 'workbench-smoke');
          localStorage.setItem('campus_session', JSON.stringify({role: 'student', name: '测试同学'}));
        }""")

        page.goto(f"{BASE_URL}/home?q=已读通知")
        page.locator(".home-search-results").get_by_text("已读通知", exact=True).wait_for()
        assert any(path.endswith("/student/assignments") and "status" not in query for path, query in requests)
        assert any(path.endswith("/tasks") and "status" not in query for path, query in requests)
        assert any(path.endswith("/notices") and "unread_only" not in query for path, query in requests)

        page.goto(f"{BASE_URL}/tasks")
        page.get_by_role("button", name="未来 7 天").wait_for()
        page.get_by_role("button", name="已完成").click()
        page.get_by_text("已提交（逾期）", exact=True).wait_for()
        page.get_by_text("已重新提交", exact=True).wait_for()
        page.get_by_label("进度 100%").first.wait_for()

        assert not errors, errors
        browser.close()


if __name__ == "__main__":
    run()
