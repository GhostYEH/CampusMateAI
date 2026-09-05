import json
import os
import re
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5174")


def payload(route, value, status=200):
    route.fulfill(status=status, content_type="application/json", body=json.dumps(value, ensure_ascii=False))


def run():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        remote_open_calls = []
        late_submit_calls = []
        late_finalize_calls = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def handle(route):
            path = urlparse(route.request.url).path
            method = route.request.method
            if path.endswith("/courses/mixed"):
                return payload(route, {"id": "mixed", "name": "混合课程", "teacher_name": "王老师", "code": "MIX-101"})
            if path.endswith("/courses/mixed/content-summary"):
                return payload(route, {"sections": []})
            if path.endswith("/courses/mixed/content"):
                return payload(route, {"items": [
                    {"id": "remote-assignment", "kind": "assignment", "title": "同步作业", "status": "completed"},
                    {"id": "remote-notice", "kind": "notice", "title": "同步通知", "description": "同步正文"},
                    {"id": "chapter-root", "kind": "chapter", "title": "第一章"},
                    {"id": "chapter-child", "kind": "document", "parent_external_id": "chapter-root", "title": "第一节"},
                    {"id": "remote-material", "kind": "document", "title": "同步资料", "can_download": False},
                ]})
            if path.endswith("/courses/mixed/resources/remote-notice/open"):
                remote_open_calls.append(path)
                return payload(route, {"url": "https://example.test/remote-notice"})
            if path.endswith("/classes"):
                return payload(route, {"items": [{"id": "class-1", "name": "一班", "teacher_name": "王老师"}]})
            if path.endswith("/classes/class-1/assignments"):
                return payload(route, {"items": [{"id": "local-assignment", "class_group_id": "class-1", "title": "本地作业", "deadline": None, "submission_status": "draft", "attachments": [{"id": "file-1", "original_filename": "作业说明.pdf", "size_bytes": 1024}]}]})
            if path.endswith("/classes/class-1/announcements"):
                return payload(route, {"items": [{"id": "local-notice", "title": "本地通知", "content": "本地正文"}]})
            if path.endswith("/assignments/late/my-submission") and method == "GET":
                return payload(route, {"id": "submission-late", "assignment_id": "late", "status": "late", "text_content": "逾期提交内容"})
            if path.endswith("/assignments/late/submissions") and method == "POST":
                late_submit_calls.append(json.loads(route.request.post_data or "{}"))
                return payload(route, {"id": "submission-late", "assignment_id": "late", "status": "late", "text_content": "逾期提交内容"})
            if path.endswith("/submissions/submission-late/submit"):
                late_finalize_calls.append(path)
                return payload(route, {"detail": "不允许重新提交"}, status=409)
            if path.endswith("/assignments/late"):
                return payload(route, {"id": "late", "title": "逾期作业", "status": "published", "description": "逾期作业说明"})
            if path.endswith("/assignments/closed/my-submission"):
                return payload(route, {"id": "submission-closed", "assignment_id": "closed", "status": "draft", "text_content": "已保存内容", "updated_at": "2026-09-05T01:00:00Z"})
            if path.endswith("/assignments/closed"):
                return payload(route, {"id": "closed", "title": "已关闭作业", "status": "closed", "description": "关闭作业说明"})
            if path.endswith("/assignments/graded/my-submission"):
                return payload(route, {"id": "submission-graded", "assignment_id": "graded", "status": "graded", "text_content": "已评分内容", "score": 92, "teacher_comment": "完成得很好", "updated_at": "2026-09-05T01:00:00Z"})
            if path.endswith("/assignments/graded"):
                return payload(route, {"id": "graded", "title": "已评分作业", "status": "published", "description": "已评分作业说明"})
            if path.endswith("/community/posts/post"):
                return payload(route, {"id": "post", "title": "评论层级", "content": "帖子正文", "category": "校园动态"})
            if path.endswith("/community/posts/post/comments"):
                return payload(route, {"items": [{"id": "root-comment", "content": "一级评论", "created_at": "2026-09-05T01:00:00Z"}, {"id": "child-comment", "content": "二级回复", "parent_comment_id": "root-comment", "created_at": "2026-09-05T01:01:00Z"}]})
            if path.endswith("/announcements/notice"):
                return payload(route, {"id": "notice", "title": "待办通知", "content": "请在周五前提交材料。", "has_read": True})
            return payload(route, {"detail": "alignment fixture"}, status=404)

        page.route("**/api/**", handle)
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
        page.wait_for_selector(".login-panel-head h2", timeout=10000)
        page.evaluate("""() => {
          localStorage.setItem('campus_access_token', 'alignment-smoke');
          localStorage.setItem('campus_session', JSON.stringify({role: 'student', name: '测试同学'}));
        }""")

        page.goto(f"{BASE_URL}/courses/mixed")
        page.locator(".course-tabs").wait_for()
        tabs = page.locator(".course-tabs")
        tabs.get_by_role("button", name="作业", exact=True).evaluate("(element) => element.click()")
        page.get_by_text("本地作业", exact=True).last.wait_for()
        page.get_by_text("同步作业", exact=True).last.wait_for()
        page.get_by_text(re.compile("同步课程内容.*已完成")).wait_for()
        tabs.get_by_role("button", name="成绩", exact=True).evaluate("(element) => element.click()")
        page.get_by_text("本地作业", exact=True).last.wait_for()
        assert page.get_by_text("同步作业", exact=True).count() == 0
        tabs.get_by_role("button", name="通知", exact=True).evaluate("(element) => element.click()")
        page.get_by_text("本地通知", exact=True).last.wait_for()
        page.get_by_text("同步通知", exact=True).last.wait_for()
        with page.expect_popup() as popup_info:
            page.locator(".course-announcement").filter(has_text="同步通知").get_by_role("button").click()
        popup = popup_info.value
        popup.close()
        page.get_by_text("同步正文", exact=True).wait_for()
        assert remote_open_calls == ["/api/v1/courses/mixed/resources/remote-notice/open"]
        tabs.get_by_role("button", name="资料", exact=True).evaluate("(element) => element.click()")
        page.get_by_text("作业说明.pdf", exact=True).last.wait_for()
        page.get_by_text("同步资料", exact=True).last.wait_for()
        tabs.get_by_role("button", name="章节", exact=True).evaluate("(element) => element.click()")
        page.get_by_role("button", name=re.compile("第一章")).click()
        page.get_by_text("第一节", exact=True).wait_for()

        page.goto(f"{BASE_URL}/tasks/assignment/closed")
        page.get_by_text("作业已关闭", exact=True).wait_for()
        assert page.get_by_label("作业提交内容").is_disabled()
        assert page.get_by_role("button", name="保存草稿").is_disabled()
        assert page.get_by_role("button", name="提交作业").is_disabled()

        page.goto(f"{BASE_URL}/tasks/assignment/late")
        page.get_by_text("已提交（逾期）", exact=True).wait_for()
        page.get_by_role("button", name="重新提交").click()
        page.get_by_text("作业已提交", exact=True).wait_for()
        assert len(late_submit_calls) == 1
        assert late_submit_calls[0]["submit"] is True
        assert late_finalize_calls == []

        page.goto(f"{BASE_URL}/tasks/assignment/graded")
        page.get_by_text("已评分", exact=True).first.wait_for()
        page.get_by_text("92", exact=True).wait_for()
        page.get_by_text("完成得很好", exact=True).wait_for()
        assert page.get_by_label("作业提交内容").is_disabled()

        page.goto(f"{BASE_URL}/community/post")
        page.locator(".comment-children").wait_for()
        page.get_by_text("二级回复", exact=True).wait_for()

        page.goto(f"{BASE_URL}/announcements/notice")
        page.get_by_role("button", name="生成待办").click()
        assert "/notifications?extract=" in page.url

        assert not errors, errors
        browser.close()


if __name__ == "__main__":
    run()
