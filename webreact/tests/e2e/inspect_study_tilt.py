import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


TASKS = {
    "items": [
        {"id": "task-1", "title": "AIGC视频小组作业", "deadline": None},
        {"id": "task-2", "title": "校园通知待办", "deadline": "2026-09-12T23:59:00"},
        {"id": "task-3", "title": "整理课程笔记", "deadline": "2026-09-14T23:59:00"},
        {"id": "task-4", "title": "完成阅读报告", "deadline": "2026-09-18T23:59:00"},
    ]
}


def mock_api(route):
    path = urlparse(route.request.url).path
    if path.endswith("/study/sessions/active"):
        route.fulfill(status=200, content_type="application/json", body="null")
    elif path.endswith("/study/sessions"):
        route.fulfill(status=200, content_type="application/json", body="[]")
    elif path.endswith("/tasks"):
        route.fulfill(status=200, content_type="application/json", body=json.dumps(TASKS))
    else:
        route.continue_()


def run():
    screenshot_path = Path(__file__).resolve().parent / "shots" / "study-tilted-card.png"
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        page.route("**/api/v1/**", mock_api)
        page.goto("http://127.0.0.1:5174/login", wait_until="networkidle")
        page.evaluate("""() => {
            localStorage.setItem('campus_access_token', 'tilt-test-token');
            localStorage.setItem('campus_session', JSON.stringify({role: 'student', name: '测试同学'}));
        }""")
        page.goto("http://127.0.0.1:5174/study", wait_until="networkidle")
        page.wait_for_selector(".study-page .study-focus-card")
        assert page.locator(".study-page .study-tilted-card").count() == 9
        page.screenshot(path=str(screenshot_path), full_page=True)
        target = page.locator(".study-focus-card .tilted-card-figure")
        box = target.bounding_box()
        assert box
        page.mouse.move(box["x"] + box["width"] * 0.8, box["y"] + box["height"] * 0.25)
        page.wait_for_timeout(400)
        transform = target.locator(".tilted-card-inner").get_attribute("style") or ""
        assert "rotateX" in transform or "rotateY" in transform or "transform" in transform
        print({
            "tiltedCardCount": page.locator(".study-page .study-tilted-card").count(),
            "focusCardBox": box,
            "focusTransform": transform,
            "screenshot": str(screenshot_path),
        })
        browser.close()


if __name__ == "__main__":
    run()
