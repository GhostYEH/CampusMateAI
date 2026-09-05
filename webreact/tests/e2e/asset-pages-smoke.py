import os

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5174")


def run():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        def fulfill(route):
            url = route.request.url
            if "/trusted-device" in url or url.endswith("/health"):
                route.fulfill(status=404, content_type="application/json", body='{"detail":"fixture"}')
                return
            if "/active" in url:
                route.fulfill(status=200, content_type="application/json", body="null")
                return
            route.fulfill(status=200, content_type="application/json", body="[]")

        page.route("**/api/**", fulfill)
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
        page.wait_for_selector(".login-panel-head h2", timeout=10000)
        page.evaluate("""() => {
          localStorage.setItem('campus_access_token', 'smoke-token');
          localStorage.setItem('campus_session', JSON.stringify({role: 'student', name: '测试同学'}));
        }""")
        cases = [
            ("/notifications", "/assets/campusmate-notice-illustration.png"),
            ("/profile", "/assets/campusmate-hero-illustration.png"),
            ("/study", "/assets/focus-study-robot.png"),
        ]
        for route, asset in cases:
            page.goto(f"{BASE_URL}{route}", wait_until="domcontentloaded")
            image = page.locator(f"img[src='{asset}']")
            image.wait_for(timeout=10000)
            assert image.evaluate("(img) => img.complete && img.naturalWidth > 0"), asset

        page.goto(f"{BASE_URL}/courses", wait_until="domcontentloaded")
        page.wait_for_selector(".courses-page", timeout=10000)
        assert page.locator(".course-asset-hero").count() == 0

        page.goto(f"{BASE_URL}/tasks", wait_until="domcontentloaded")
        page.get_by_role("button", name="导入材料").click()
        image = page.locator(".import-hero img[src='/assets/campusmate-hero-illustration.png']")
        image.wait_for(timeout=10000)
        assert image.evaluate("(img) => img.complete && img.naturalWidth > 0")
        browser.close()


if __name__ == "__main__":
    run()
