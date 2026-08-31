import os
from pathlib import Path

from playwright.sync_api import sync_playwright


output_dir = Path("../artifacts/digital-human")
output_dir.mkdir(parents=True, exist_ok=True)
base_url = os.environ.get("DIGITAL_HUMAN_VISUAL_URL", "http://127.0.0.1:4194")

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        headless=True,
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
    )
    page = browser.new_page(viewport={"width": 320, "height": 320}, device_scale_factor=1)
    console_errors: list[str] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.goto(f"{base_url}/digital-human/mobile.html?layout=harmony&fallback=1")
    page.wait_for_load_state("networkidle")

    avatar = page.locator("#compat-avatar")
    assert avatar.is_visible()
    assert page.locator("#avatar-frame").is_hidden()
    bounds = avatar.bounding_box()
    assert bounds is not None and bounds["width"] == 320 and bounds["height"] == 320

    initial_transform = page.locator(".compat-rig").evaluate("element => getComputedStyle(element).transform")
    page.wait_for_timeout(450)
    moving_transform = page.locator(".compat-rig").evaluate("element => getComputedStyle(element).transform")
    assert initial_transform != moving_transform
    page.screenshot(path=str(output_dir / "harmony-idle.png"))

    avatar.evaluate("element => element.classList.add('speaking')")
    page.add_style_tag(content="""
      #compat-avatar {
        --mouth-open: 1 !important;
        --blink: 1 !important;
        --avatar-rotate: 2deg !important;
        --avatar-shift-y: -1% !important;
      }
    """)
    page.screenshot(path=str(output_dir / "harmony-speaking-blink.png"))
    print({"console_errors": console_errors})
    assert console_errors == []

    android_page = browser.new_page(viewport={"width": 320, "height": 320}, device_scale_factor=1)
    android_page.goto(f"{base_url}/digital-human/mobile.html?embed=1&fallback=1")
    android_page.wait_for_load_state("networkidle")
    android_avatar = android_page.locator("#compat-avatar")
    assert android_avatar.is_visible()
    android_bounds = android_avatar.bounding_box()
    assert android_bounds is not None and android_bounds["width"] == 320 and android_bounds["height"] == 320
    android_page.screenshot(path=str(output_dir / "android-idle.png"))
    android_page.close()

    compact_page = browser.new_page(viewport={"width": 148, "height": 148}, device_scale_factor=1)
    compact_page.goto(f"{base_url}/digital-human/mobile.html?layout=harmony&fallback=1")
    compact_page.wait_for_load_state("networkidle")
    compact_avatar = compact_page.locator("#compat-avatar")
    compact_avatar.evaluate("element => element.classList.add('speaking')")
    compact_page.add_style_tag(content="""
      #compat-avatar {
        --mouth-open: 1 !important;
        --blink: 1 !important;
        --avatar-rotate: 0deg !important;
        --avatar-shift-y: 0% !important;
        --avatar-scale: 1 !important;
      }
    """)
    compact_bounds = compact_avatar.bounding_box()
    left_eye_bounds = compact_page.locator(".compat-eye.left").bounding_box()
    right_eye_bounds = compact_page.locator(".compat-eye.right").bounding_box()
    mouth_bounds = compact_page.locator("#compat-mouth").bounding_box()
    assert compact_bounds is not None and compact_bounds["width"] == 148 and compact_bounds["height"] == 148
    assert left_eye_bounds is not None and 55 < left_eye_bounds["x"] + left_eye_bounds["width"] / 2 < 68
    assert right_eye_bounds is not None and 80 < right_eye_bounds["x"] + right_eye_bounds["width"] / 2 < 93
    assert 33 < left_eye_bounds["y"] + left_eye_bounds["height"] / 2 < 45
    assert mouth_bounds is not None and 70 < mouth_bounds["x"] + mouth_bounds["width"] / 2 < 78
    assert 53 < mouth_bounds["y"] + mouth_bounds["height"] / 2 < 65
    compact_page.screenshot(path=str(output_dir / "harmony-speaking-blink-148.png"))
    compact_page.close()

    reduced_page = browser.new_page(viewport={"width": 320, "height": 320}, device_scale_factor=1)
    reduced_page.goto(f"{base_url}/digital-human/mobile.html?embed=1&fallback=1&reduceMotion=1")
    reduced_page.wait_for_load_state("networkidle")
    reduced_rig = reduced_page.locator(".compat-rig")
    reduced_initial = reduced_rig.evaluate("element => getComputedStyle(element).transform")
    reduced_page.wait_for_timeout(450)
    reduced_later = reduced_rig.evaluate("element => getComputedStyle(element).transform")
    assert reduced_initial == reduced_later
    reduced_page.close()
    browser.close()

print({"screenshots": [str(path) for path in output_dir.glob("*.png")]})
