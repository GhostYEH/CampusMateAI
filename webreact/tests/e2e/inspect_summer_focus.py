from pathlib import Path

from playwright.sync_api import sync_playwright


SCREENSHOT = Path("summer-focus-room-browser.png")


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    context.add_init_script(
        """
        localStorage.setItem('campus_access_token', 'browser-test-token');
        localStorage.setItem('campus_session', JSON.stringify({
          id: 'browser-test', role: 'student', name: '浏览器检查', email: 'browser@example.com'
        }));
        """
    )
    page = context.new_page()
    page.goto("http://127.0.0.1:5174/study", wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        # The guarded app retries unavailable API calls during the local visual smoke check.
        pass
    page.wait_for_timeout(1500)
    for attempt in range(2):
        try:
            page.locator(".study-summer-room").wait_for(state="attached", timeout=45000)
            break
        except Exception:
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
    page.wait_for_timeout(1500)

    room = page.locator(".study-summer-room").bounding_box()
    nav = page.locator(".floating-nav").bounding_box()
    viewport_height = page.viewport_size["height"]
    print({"viewport": viewport_height, "room": room, "nav": nav})
    assert room and nav
    assert room["width"] > 500, f"room width {room['width']} too narrow for full-width grid"
    assert page.locator(".study-summer-focus").count() == 1
    assert page.locator(".study-summer-atmosphere").count() == 1
    assert page.locator(".study-summer-todos").count() == 1
    assert nav["y"] + nav["height"] > viewport_height - 130, f"nav bottom {nav['y'] + nav['height']} not near viewport {viewport_height}"
    assert room["y"] < nav["y"], f"room top {room['y']} not above nav top {nav['y']}"

    page.screenshot(path=str(SCREENSHOT), full_page=True)
    print({
        "url": page.url,
        "room": room,
        "nav": nav,
        "scene_buttons": page.locator(".study-summer-scenes button").count(),
        "title": page.locator("#study-summer-title").inner_text(),
        "screenshot": str(SCREENSHOT.resolve()),
    })
    browser.close()
