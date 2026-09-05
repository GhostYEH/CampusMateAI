import json
import os
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5174")


def run():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def fulfill(route, value):
            route.fulfill(status=200, content_type="application/json", body=json.dumps(value))

        def handle(route):
            path = urlparse(route.request.url).path
            if path.endswith("/health") or path.endswith("/auth/trusted-device/auto-login"):
                route.fulfill(status=404, content_type="application/json", body='{"detail":"fixture"}')
            elif path.endswith("/study/sessions/active"):
                fulfill(route, None)
            elif path.endswith("/study/sessions"):
                fulfill(route, {"items": []})
            else:
                fulfill(route, {"items": []})

        page.route("**/api/**", handle)
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
        page.evaluate("""() => {
          localStorage.setItem('campus_access_token', 'white-noise-test');
          localStorage.setItem('campus_session', JSON.stringify({role: 'student', name: '测试同学'}));
        }""")
        page.reload(wait_until="domcontentloaded")
        page.goto(f"{BASE_URL}/study")
        page.wait_for_load_state("networkidle")

        control = page.locator(".white-noise-control")
        control.wait_for(timeout=10000)
        slider = page.get_by_role("slider", name="白噪音音量")
        assert slider.get_attribute("aria-valuenow") == "32"
        slider.press("ArrowRight")
        assert slider.get_attribute("aria-valuenow") == "35"
        box = slider.bounding_box()
        page.mouse.move(box["x"] + box["width"] * 0.75, box["y"] + box["height"] / 2)
        page.mouse.down()
        page.mouse.move(box["x"] + box["width"] * 0.75, box["y"] + box["height"] / 2)
        page.mouse.up()
        assert slider.get_attribute("aria-valuenow") == "75"
        page.get_by_role("button", name="降低音量").click()
        assert slider.get_attribute("aria-valuenow") == "70"
        page.get_by_role("button", name="开启白噪音").click()
        assert page.get_by_role("button", name="关闭白噪音").get_attribute("aria-pressed") == "true"
        assert "柔和播放中" in control.inner_text()
        assert not errors, errors
        browser.close()


if __name__ == "__main__":
    run()
