import json
import os
import time
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5174")


def wait_visible(page, locator, timeout_ms=15000, what="element"):
    """Poll until the first matching element is visible. Deterministic
    replacement for locator.wait_for(state='visible'), which is flaky under
    Vite dev-server latency on this setup."""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        try:
            if locator.count() > 0 and locator.first.is_visible():
                return
        except Exception:
            pass
        page.wait_for_timeout(200)
    raise AssertionError(f"{what} not visible within {timeout_ms}ms")


def build_fixture():
    now = datetime.now()
    deadline_a = (now + timedelta(hours=2)).isoformat()
    deadline_p = (now + timedelta(hours=5)).isoformat()
    weekday = now.isoweekday()  # 1 = Monday ... 7 = Sunday
    dashboard = {
        "due_soon_assignments": [
            {"id": "a1", "title": "高等数学作业", "course_name": "高等数学", "deadline": deadline_a},
        ],
        "due_soon_personal_tasks": [
            {"id": "p1", "title": "整理课堂笔记", "deadline": deadline_p},
        ],
        "pending_assignment_count": 1,
        "pending_personal_task_count": 1,
        "unread_announcement_count": 2,
        "enrolled_course_count": 4,
    }
    schedule_items = {
        "items": [
            {"id": "s1", "course_name": "高等数学", "weekday": weekday, "start_section": 1, "end_section": 2, "location": "教1-201"},
            {"id": "s2", "course_name": "大学英语", "weekday": weekday, "start_section": 3, "end_section": 3, "location": "教2-305"},
        ]
    }
    return dashboard, schedule_items


def run():
    dashboard_fixture, schedule_fixture = build_fixture()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page_errors = []
        failed_local_assets = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on(
            "requestfailed",
            lambda request: failed_local_assets.append(request.url)
            if "/landing-pages/inner-green" in request.url
            else None,
        )

        def api_route(route):
            url = route.request.url
            if "/dashboard/student" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps(dashboard_fixture))
            elif "/edu/schedule/items" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps(schedule_fixture))
            else:
                route.fulfill(status=404, content_type="application/json", body='{"detail":"sylva smoke fixture"}')

        page.route("**/api/**", api_route)
        page.add_init_script(
            """
            // Keep the exact scene responsive under headless Chromium's software renderer.
            window.requestAnimationFrame = callback =>
              window.setTimeout(() => callback(performance.now()), 50);
            localStorage.setItem('campus_access_token', 'sylva-smoke-token');
            localStorage.setItem('campus_session', JSON.stringify({role: 'student', name: '测试同学'}));
            """
        )

        page.goto(f"{BASE_URL}/home", wait_until="networkidle", timeout=30_000)
        page.wait_for_timeout(2500)
        print("desktop page loaded", flush=True)

        # ── fixed background layer + three.js scene ──────────────────────
        background = page.locator(".sylva-home-hero.sylva-scene-background")
        if background.count() == 0:
            raise AssertionError(
                {
                    "url": page.url,
                    "title": page.title(),
                    "body": page.locator("body").inner_text()[:1200],
                    "page_errors": page_errors,
                }
            )
        iframe = page.locator(".sylva-scene-background iframe")
        wait_visible(page, iframe, 15000, "sylva iframe")
        assert iframe.get_attribute("src") == "/landing-pages/inner-green-3d.html"

        scene = iframe.element_handle().content_frame()
        scene.wait_for_load_state("domcontentloaded")
        canvas = scene.query_selector("#scene")
        assert canvas is not None
        scene_pixels = canvas.evaluate(
            "canvas => ({width: canvas.width, height: canvas.height, engine: canvas.dataset.engine})"
        )
        assert scene_pixels["width"] > 0 and scene_pixels["height"] > 0
        assert scene_pixels["engine"] == "three.js r149"
        headline = scene.query_selector(".headline")
        assert headline is not None
        assert headline.evaluate("el => getComputedStyle(el).display") == "none"
        assert scene.query_selector(".dock-wrap") is None
        bg_style = background.evaluate("el => getComputedStyle(el).position")
        assert bg_style == "fixed"
        bg_box = background.bounding_box()
        assert bg_box and abs(bg_box["x"]) < 2 and abs(bg_box["y"]) < 2
        assert abs(bg_box["width"] - 1440) < 2 and abs(bg_box["height"] - 900) < 2
        print("desktop scene verified", flush=True)

        # ── first viewport: CampusMate workbench ─────────────────────────
        overview = page.locator(".sylva-campus-overview")
        wait_visible(page, overview, 10000, "campus overview")
        title = page.locator(".sylva-overview-title")
        assert title.is_visible() and len(title.inner_text().strip()) > 0
        primary = page.locator(".sylva-overview-primary")
        assert primary.is_visible()
        assert page.locator(".sylva-priority-card").count() == 1
        assert page.get_by_role("heading", name="优先事项").count() == 1
        assert page.locator(".sylva-priority-list > button").count() >= 1
        assert page.locator(".sylva-schedule-card").count() == 1
        assert page.locator(".sylva-schedule-card").inner_text().startswith("今日课程表")
        assert page.locator(".sylva-schedule-days > span.today").count() == 1
        assert page.locator(".sylva-schedule-today > button").count() == 2
        assert page.locator(".sylva-overview-pulse").count() == 1
        assert page.locator(".sylva-overview-pulse .home-learning-pulse").count() == 1
        assert page.locator(".sylva-dashboard .simple-priority-panel").count() == 0
        assert page.locator(".sylva-scene-stat").count() == 3
        print("first viewport workbench verified", flush=True)

        # ── global liquid-glass navigation ───────────────────────────────
        global_nav = page.locator(".floating-nav")
        global_nav.wait_for(state="visible")
        assert global_nav.locator(".floating-nav-button").count() == 10
        assert global_nav.get_by_role("button", name="首页").get_attribute("aria-current") == "page"
        assert global_nav.get_attribute("data-contrast") is None
        assert global_nav.get_attribute("data-ogui-tone") is None
        assert global_nav.locator(".floating-nav-glass").count() == 1
        assert global_nav.locator(".sylva-liquid-plate, canvas").count() == 0
        glass_filter = global_nav.locator(".floating-nav-glass").evaluate(
            "el => getComputedStyle(el).backdropFilter || getComputedStyle(el).webkitBackdropFilter"
        )
        assert glass_filter and glass_filter != "none", glass_filter
        nav_color = page.locator(".floating-nav-button").first.evaluate("el => getComputedStyle(el).color")
        assert nav_color and nav_color != "rgba(0, 0, 0, 0)", nav_color
        print(f"global primary navigation color={nav_color}", flush=True)

        # ── clicking a priority item opens its task route ────────────────
        page.locator(".sylva-priority-list > button").first.click()
        page.wait_for_url(f"{BASE_URL}/tasks/assignment/a1", timeout=10_000)
        print("priority item route verified", flush=True)

        # ── schedule card leads to the academic schedule ─────────────────
        page.goto(f"{BASE_URL}/home", wait_until="networkidle", timeout=30_000)
        page.wait_for_timeout(2500)
        schedule_button = page.locator(".sylva-schedule-today > button").first
        wait_visible(page, schedule_button, 10000, "schedule course button")
        schedule_button.click()
        page.wait_for_url(f"{BASE_URL}/profile/academic", timeout=10_000)
        print("schedule card route verified", flush=True)

        # ── after scrolling one viewport the background stays pinned ─────
        page.goto(f"{BASE_URL}/home", wait_until="networkidle", timeout=30_000)
        page.wait_for_timeout(2500)
        wait_visible(page, background, 15000, "fixed background")
        before_box = background.bounding_box()
        page.evaluate("window.scrollTo(0, window.innerHeight)")
        page.wait_for_timeout(300)
        after_box = background.bounding_box()
        assert after_box and abs(after_box["x"] - before_box["x"]) < 2
        assert after_box and abs(after_box["y"] - before_box["y"]) < 2
        assert abs(after_box["width"] - 1440) < 2 and abs(after_box["height"] - 900) < 2
        overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert overflow <= 0, f"desktop horizontal overflow: {overflow}"
        print("desktop scroll pinned verified", flush=True)

        # ── mobile: 390×844 ──────────────────────────────────────────────
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(f"{BASE_URL}/home", wait_until="networkidle", timeout=30_000)
        page.wait_for_timeout(2500)
        print("mobile page loaded", flush=True)
        mobile_bg = page.locator(".sylva-home-hero.sylva-scene-background")
        wait_visible(page, mobile_bg, 15000, "mobile background")
        mobile_iframe = mobile_bg.locator("iframe")
        mobile_scene = mobile_iframe.element_handle().content_frame()
        mobile_scene.wait_for_load_state("domcontentloaded")
        assert mobile_scene.query_selector("#scene") is not None
        mobile_box = mobile_bg.bounding_box()
        assert mobile_box and abs(mobile_box["width"] - 390) < 2
        assert abs(mobile_box["height"] - 844) < 2
        assert page.locator(".floating-nav").is_visible()
        assert page.locator(".floating-nav-button").count() == 9
        assert page.locator(".sylva-overview-primary").is_visible()
        assert page.locator(".sylva-priority-card").is_visible()
        overflow_m = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert overflow_m <= 0, f"mobile horizontal overflow: {overflow_m}"
        print("mobile scene verified", flush=True)

        # ── narrow: 320×720 ──────────────────────────────────────────────
        page.set_viewport_size({"width": 320, "height": 720})
        page.goto(f"{BASE_URL}/home", wait_until="networkidle", timeout=30_000)
        page.wait_for_timeout(2500)
        narrow_bg = page.locator(".sylva-home-hero.sylva-scene-background")
        wait_visible(page, narrow_bg, 15000, "narrow background")
        narrow_box = narrow_bg.bounding_box()
        assert narrow_box and abs(narrow_box["width"] - 320) < 2
        assert page.locator(".sylva-overview-primary").is_visible()
        assert page.locator(".sylva-schedule-card").is_visible()
        overflow_n = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert overflow_n <= 0, f"narrow horizontal overflow: {overflow_n}"
        print("narrow scene verified", flush=True)

        assert not failed_local_assets, failed_local_assets
        assert not page_errors, page_errors
        browser.close()
        print("Sylva homepage smoke passed")


if __name__ == "__main__":
    run()
