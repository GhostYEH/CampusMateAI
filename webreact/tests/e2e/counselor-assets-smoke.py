import os

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5174")


def run():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def fulfill(route):
            url = route.request.url
            if "/trusted-device" in url or url.endswith("/health"):
                route.fulfill(status=404, content_type="application/json", body='{"detail":"fixture"}')
                return
            if "/tasks" in url:
                route.fulfill(status=200, content_type="application/json", body='{"items":[]}')
                return
            route.fulfill(status=404, content_type="application/json", body='{"detail":"frontend smoke fixture"}')

        page.route("**/api/**", fulfill)
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=10000)
        page.wait_for_selector(".login-panel-head h2", timeout=10000)
        page.evaluate("""() => {
          localStorage.setItem('campus_access_token', 'smoke-token');
          localStorage.setItem('campus_session', JSON.stringify({role: 'student', name: '测试同学'}));
        }""")
        page.goto(f"{BASE_URL}/counselor", wait_until="domcontentloaded", timeout=10000)
        page.wait_for_selector(".counselor-reference", timeout=10000)

        assert page.locator(".app-counselor-prism").count() == 1
        assert page.locator(".app-counselor-prism canvas").count() == 1
        assert page.locator(".counselor-ripple canvas").count() == 1
        assert page.locator("img[src='/assets/counselor-campus-hero-reference.png']").count() == 0
        assert page.locator(".counselor-reference-grid").count() == 1
        assert page.locator(".counselor-session-panel").count() == 1
        assert page.locator(".counselor-chat-panel").count() == 1
        assert page.locator(".counselor-digital-human").count() == 1
        assert page.locator("iframe[src='/digital-human/index.html']").count() == 1
        assert page.get_by_role("button", name="新建对话").is_visible()
        assert page.get_by_role("button", name="换一换").is_visible()
        assert page.get_by_role("button", name="生成个性化复习计划").is_visible()
        assert page.get_by_role("button", name="制定每日任务清单").is_visible()
        assert page.get_by_role("button", name="推荐复习资料").is_visible()
        assert page.get_by_role("button", name="更多建议").is_visible()
        assert page.get_by_text("服务条款").is_visible()
        assert page.get_by_text("隐私政策").is_visible()
        assert not errors, errors
        browser.close()


if __name__ == "__main__":
    run()
