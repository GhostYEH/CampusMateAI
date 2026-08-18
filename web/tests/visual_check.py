from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("artifacts/web-ui")
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe")
    page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    page.add_init_script("""localStorage.setItem('campus_access_token','visual'); localStorage.setItem('campus_session', JSON.stringify({role:'student',name:'陈同学(演示)',avatar_url:'/assets/generated/home-reference-student-avatar.png'}));""")
    errors = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    for path in ("/tasks", "/community", "/community/create"):
        page.goto(f"http://127.0.0.1:5173{path}")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(OUT / (path.strip('/').replace('/', '-') + ".png")), full_page=True)
    page.goto("http://127.0.0.1:5173/tasks")
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="新建待办").click()
    page.wait_for_selector(".student-modal")
    assert page.get_by_role("heading", name="新建个人待办").is_visible()
    page.get_by_role("button", name="取消").click()
    page.goto("http://127.0.0.1:5173/community/create")
    page.wait_for_load_state("networkidle")
    page.locator('input[placeholder="一句话说清主题"]').fill("周末校园活动分享")
    page.locator('textarea[placeholder*="详细描述"]').fill("欢迎大家来参加本周末的校园活动。")
    page.get_by_role("button", name="预览").click()
    page.wait_for_selector(".post-preview-modal")
    page.screenshot(path=str(OUT / "create-preview.png"), full_page=True)
    print({"console_errors": errors, "screenshots": [str(p) for p in OUT.glob("*.png")]})
    browser.close()
