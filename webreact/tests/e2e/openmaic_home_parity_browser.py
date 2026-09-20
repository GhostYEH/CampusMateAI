"""Compare the reference root and CampusMate courses home in two browser contexts."""

from __future__ import annotations

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


REFERENCE_URL = os.getenv("REFERENCE_BASE_URL", "http://127.0.0.1:3000/")
APP_URL = os.getenv("WEB_BASE_URL", "http://127.0.0.1:5174/")


def metrics(page):
    return page.evaluate("""() => ({
      viewport: { width: innerWidth, height: innerHeight },
      scrollWidth: document.documentElement.scrollWidth,
      textarea: document.querySelector('textarea')?.getBoundingClientRect().toJSON() || null,
      composer: document.querySelector('.openmaic-reference-composer')?.getBoundingClientRect().toJSON() || null,
      brand: document.querySelector('.openmaic-reference__brand')?.getBoundingClientRect().toJSON() || null,
      recent: document.querySelector('.openmaic-reference-recent')?.getBoundingClientRect().toJSON() || null,
      ancestors: [...(document.querySelector('.openmaic-reference-composer')?.parentElement?.parentElement?.parentElement ? [document.querySelector('.openmaic-reference-composer').parentElement, document.querySelector('.openmaic-reference-composer').parentElement.parentElement, document.querySelector('.openmaic-reference-composer').parentElement.parentElement.parentElement] : [])].map(el => ({tag: el.tagName, className: el.className, rect: el.getBoundingClientRect().toJSON(), maxWidth: getComputedStyle(el).maxWidth})),
      horizontalOverflow: document.documentElement.scrollWidth > innerWidth,
    })""")


def observe(page, label):
    errors = []
    page.on("pageerror", lambda error: errors.append(f"pageerror:{error}"))
    page.on("console", lambda message: errors.append(f"console:{message.text}") if message.type == "error" else None)
    responses = []
    page.on("response", lambda response: responses.append(response.status) if response.status >= 400 else None)
    page.wait_for_timeout(1800)
    result = {"label": label, "url": page.url, "metrics": metrics(page), "errors": errors, "http_errors": responses}
    shots = os.getenv("E2E_SHOTS_DIR")
    if shots:
        Path(shots).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(shots) / f"{label}.png"), full_page=True)
    return result


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    reference = browser.new_context(viewport={"width": 1440, "height": 900})
    app = browser.new_context(viewport={"width": 1440, "height": 900})
    ref_page = reference.new_page()
    app_page = app.new_page()
    ref_page.goto(REFERENCE_URL, wait_until="domcontentloaded")
    app_page.goto(f"{APP_URL.rstrip('/')}/login", wait_until="domcontentloaded")
    app_page.locator("form input").nth(0).fill(os.getenv("CAMPUSMATE_USER", "student_demo"))
    app_page.locator("form input").nth(1).fill(os.getenv("CAMPUSMATE_PASSWORD", "Demo123456"))
    app_page.locator('form button:has-text("登录")').click()
    app_page.wait_for_url("**/home", timeout=25000)
    app_page.goto(f"{APP_URL.rstrip('/')}/courses", wait_until="domcontentloaded")
    print(json.dumps({"reference": observe(ref_page, "reference"), "app": observe(app_page, "app")}, ensure_ascii=False, indent=2))
    browser.close()
