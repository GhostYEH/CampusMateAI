import os

from playwright.sync_api import sync_playwright


base_url = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:4175")


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 960}, device_scale_factor=2)

    def fulfill(route):
        url = route.request.url
        if "/trusted-device" in url or url.endswith("/health"):
            route.fulfill(status=404, content_type="application/json", body='{"detail":"fixture"}')
        elif "/active" in url:
            route.fulfill(status=200, content_type="application/json", body="null")
        else:
            route.fulfill(status=200, content_type="application/json", body="[]")

    page.route("**/api/**", fulfill)
    page.goto(f"{base_url}/login", wait_until="domcontentloaded")
    page.evaluate("""() => {
      localStorage.setItem("campus_access_token", "performance-test");
      localStorage.setItem("campus_session", JSON.stringify({ role: "student", name: "测试同学" }));
    }""")
    page.goto(f"{base_url}/courses", wait_until="domcontentloaded")
    canvas = page.locator(".courses-grainient canvas")
    canvas.wait_for(timeout=10000)

    assert canvas.evaluate("node => [node.width, node.height]") == [1728, 1152]
    assert canvas.evaluate("node => [node.clientWidth, node.clientHeight]") == [1440, 960]
    assert page.locator(".courses-grainient").evaluate("node => getComputedStyle(node).pointerEvents") == "none"
    browser.close()
