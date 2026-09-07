import os

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5174")


def run():
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
        page.route(
            "**/api/**",
            lambda route: route.fulfill(
                status=404,
                content_type="application/json",
                body='{"detail":"sylva smoke fixture"}',
            ),
        )
        page.add_init_script(
            """
            // Keep the exact scene responsive under headless Chromium's software renderer.
            window.requestAnimationFrame = callback =>
              window.setTimeout(() => callback(performance.now()), 50);
            localStorage.setItem('campus_access_token', 'sylva-smoke-token');
            localStorage.setItem('campus_session', JSON.stringify({role: 'student', name: '测试同学'}));
            localStorage.setItem('campus_dashboard_style', 'classic');
            """
        )

        page.goto(f"{BASE_URL}/home", wait_until="networkidle", timeout=30_000)
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
        iframe.wait_for(state="visible", timeout=15_000)
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
        # the English editorial layer is hidden; only the living scene remains
        headline = scene.query_selector(".headline")
        assert headline is not None
        assert headline.evaluate("el => getComputedStyle(el).display") == "none"
        assert scene.query_selector(".dock-wrap") is None
        assert not scene.query_selector_all(".dock [data-dock]")
        # background is truly fixed at the viewport origin
        bg_style = background.evaluate("el => getComputedStyle(el).position")
        assert bg_style == "fixed"
        bg_box = background.bounding_box()
        assert bg_box and abs(bg_box["x"]) < 2 and abs(bg_box["y"]) < 2
        assert abs(bg_box["width"] - 1440) < 2 and abs(bg_box["height"] - 900) < 2
        print("desktop scene verified", flush=True)

        # ── first viewport shows CampusMate business content ─────────────
        overview = page.locator(".sylva-campus-overview")
        overview.wait_for(state="visible", timeout=10_000)
        title = page.locator(".sylva-overview-title")
        assert title.is_visible()
        assert len(title.inner_text().strip()) > 0
        primary = page.locator(".sylva-overview-primary")
        assert primary.is_visible()
        assert page.locator(".sylva-rhythm-card").count() == 1
        assert page.locator(".sylva-next-card").count() == 1
        assert page.locator(".sylva-scene-stat").count() >= 2
        assert page.get_by_role("heading", name="今日学习节奏").count() == 1
        assert page.get_by_role("heading", name="下一件事").count() == 1

        # ── existing global navigation preserved ─────────────────────────
        global_nav = page.locator(".floating-nav")
        global_nav.wait_for(state="visible")
        assert global_nav.locator(".floating-nav-button").count() == 8
        assert global_nav.get_by_role("button", name="首页").get_attribute("aria-current") == "page"

        # ── primary action navigates to a real existing route ────────────
        primary.click()
        page.wait_for_url(f"{BASE_URL}/study", timeout=10_000)
        print("primary action route verified", flush=True)

        # ── after scrolling one viewport the background stays pinned ─────
        page.goto(f"{BASE_URL}/home", wait_until="networkidle", timeout=30_000)
        background.wait_for(state="visible", timeout=15_000)
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
        print("mobile page loaded", flush=True)
        mobile_bg = page.locator(".sylva-home-hero.sylva-scene-background")
        mobile_bg.wait_for(state="visible", timeout=15_000)
        mobile_iframe = mobile_bg.locator("iframe")
        mobile_scene = mobile_iframe.element_handle().content_frame()
        mobile_scene.wait_for_load_state("domcontentloaded")
        assert mobile_scene.query_selector("#scene") is not None
        mobile_box = mobile_bg.bounding_box()
        assert mobile_box and abs(mobile_box["width"] - 390) < 2
        assert abs(mobile_box["height"] - 844) < 2
        assert page.locator(".floating-nav").is_visible()
        assert page.locator(".floating-nav-button").count() == 8
        assert page.locator(".sylva-overview-primary").is_visible()
        overflow_m = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert overflow_m <= 0, f"mobile horizontal overflow: {overflow_m}"
        print("mobile scene verified", flush=True)

        # ── narrow: 320×720 ──────────────────────────────────────────────
        page.set_viewport_size({"width": 320, "height": 720})
        page.goto(f"{BASE_URL}/home", wait_until="networkidle", timeout=30_000)
        narrow_bg = page.locator(".sylva-home-hero.sylva-scene-background")
        narrow_bg.wait_for(state="visible", timeout=15_000)
        narrow_box = narrow_bg.bounding_box()
        assert narrow_box and abs(narrow_box["width"] - 320) < 2
        assert page.locator(".sylva-overview-primary").is_visible()
        overflow_n = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert overflow_n <= 0, f"narrow horizontal overflow: {overflow_n}"
        print("narrow scene verified", flush=True)

        assert not failed_local_assets, failed_local_assets
        assert not page_errors, page_errors
        browser.close()
        print("Sylva homepage smoke passed")


if __name__ == "__main__":
    run()
