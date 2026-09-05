import os

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5174")


ROUTES = [
    "/home", "/courses", "/courses/1", "/tasks", "/tasks/personal/1",
    "/community", "/community/create", "/community/1", "/university",
    "/counselor", "/notifications", "/announcements/1", "/study", "/exams",
    "/exams/1", "/exams/1/edit", "/profile", "/profile/favorites",
    "/profile/chaoxing", "/profile/academic", "/profile/settings",
]


def run():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("**/api/**", lambda route: route.fulfill(status=404, content_type="application/json", body='{"detail":"frontend smoke fixture"}'))
        page.goto(f"{BASE_URL}/home", wait_until="domcontentloaded", timeout=10000)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_selector(".login-panel-head h2", timeout=10000)
        assert page.url.endswith("/login"), page.url
        assert page.get_by_role("heading", name="登录 CampusMate").is_visible()

        smoke_token = os.environ.get("WEBREACT_SMOKE_TOKEN", "smoke-token")
        page.evaluate("""(token) => {
          localStorage.setItem('campus_access_token', token);
          localStorage.setItem('campus_session', JSON.stringify({role: 'student', name: '测试同学'}));
        }""", smoke_token)
        for viewport in (
            {"width": 1440, "height": 900}, {"width": 1024, "height": 768},
            {"width": 768, "height": 1024}, {"width": 320, "height": 720},
        ):
            page.set_viewport_size(viewport)
            for route in ROUTES + ["/", "/profile/files", "/profile/learning", "/profile/id-card"]:
                page.goto(f"{BASE_URL}{route}", wait_until="domcontentloaded", timeout=10000)
                page.wait_for_load_state("domcontentloaded")
                try:
                    page.wait_for_selector("main h1", timeout=10_000)
                except Exception as error:
                    raise AssertionError(f"{route}: {error}") from error
                page.wait_for_timeout(100)
                assert page.locator("main").count() > 0, route
                assert page.locator("h1").count() > 0, route
                assert page.locator(".floating-nav").count() == 1, route
                assert page.locator(".sidebar").count() == 0, route
            if viewport["width"] < 700:
                page.goto(f"{BASE_URL}/home", wait_until="domcontentloaded", timeout=10000)
                assert page.locator(".floating-nav").count() == 1
                assert page.locator(".sidebar").count() == 0
            else:
                page.goto(f"{BASE_URL}/home", wait_until="domcontentloaded", timeout=10000)
                dock = page.locator(".floating-nav")
                assert dock.get_by_role("button", name="首页").is_visible()
                assert dock.get_by_role("button", name="待办与作业").is_visible()
        assert not errors, errors
        browser.close()


if __name__ == "__main__":
    run()
