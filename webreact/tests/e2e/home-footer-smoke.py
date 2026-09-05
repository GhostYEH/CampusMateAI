import json
import os

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5174")


def run():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        def fulfill_api(route):
            if "dashboard/student" not in route.request.url:
                route.fulfill(status=404, content_type="application/json", body='{"detail":"footer smoke fixture"}')
                return
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({
                    "pending_assignment_count": 2,
                    "pending_personal_task_count": 1,
                    "unread_announcement_count": 3,
                    "week_focus_minutes": 42,
                    "course_count": 6,
                    "due_soon_assignments": [],
                    "due_soon_personal_tasks": [],
                    "today_schedule": [],
                }),
            )

        page.route("**/api/v1/**", fulfill_api)
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
        page.wait_for_selector(".login-panel-head h2")
        page.evaluate("""() => {
            localStorage.setItem('campus_access_token', 'footer-smoke-token');
            localStorage.setItem('campus_session', JSON.stringify({role: 'student', name: '测试同学'}));
        }""")
        page.goto(f"{BASE_URL}/home", wait_until="networkidle")
        page.wait_for_selector(".home-footer-brand")
        assert page.locator(".simple-quick-section").get_by_role("heading", name="需要时再打开").is_visible()
        assert page.get_by_text("关注微信公众号").is_visible()
        assert page.locator(".home-foreground").count() == 1
        underlay = page.locator(".home-brand-underlay")
        underlay_style = underlay.evaluate("element => { const style = getComputedStyle(element); const rect = element.getBoundingClientRect(); return { position: style.position, bottom: style.bottom, height: rect.height, viewportHeight: window.innerHeight }; }")
        assert underlay_style["position"] == "fixed"
        assert underlay_style["bottom"] == "0px"
        assert abs(underlay_style["viewportHeight"] - (underlay_style["height"] + underlay.bounding_box()["y"])) < 2
        assert page.locator(".home-foreground .home-footer-info").count() == 1
        assert page.locator(".home-footer-brand canvas").count() == 1

        for viewport in ({"width": 768, "height": 900}, {"width": 320, "height": 720}):
            page.set_viewport_size(viewport)
            page.wait_for_timeout(100)
            assert page.locator(".student-quick-grid").count() == 1
            assert page.locator(".home-footer-brand").count() == 1

        browser.close()
        print("home footer runtime smoke passed")


if __name__ == "__main__":
    run()
