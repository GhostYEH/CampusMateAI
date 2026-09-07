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
        iframe = page.locator(".sylva-home-hero iframe")
        if iframe.count() == 0:
            raise AssertionError(
                {
                    "url": page.url,
                    "title": page.title(),
                    "body": page.locator("body").inner_text()[:1200],
                    "page_errors": page_errors,
                }
            )
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
        dock_items = scene.query_selector_all(".dock [data-dock]")
        assert len(dock_items) == 5
        assert scene.query_selector(".dock-wrap").evaluate(
            "element => getComputedStyle(element).display"
        ) == "none"
        scene_copy = scene.query_selector(".headline")
        assert scene_copy is not None
        assert "Step into" in scene_copy.inner_text()
        assert "the living world" in scene_copy.inner_text()
        explore_button = scene.query_selector(".liquid-button--explore")
        assert explore_button is not None
        global_nav = page.locator(".floating-nav")
        global_nav.wait_for(state="visible")
        assert global_nav.locator(".floating-nav-button").count() == 8
        assert global_nav.get_by_role("button", name="首页").get_attribute("aria-current") == "page"

        hero_box = page.locator(".sylva-home-hero").bounding_box()
        assert hero_box and abs(hero_box["height"] - 900) < 2
        print("desktop scene verified", flush=True)

        explore_button.evaluate("button => button.click()")
        page.wait_for_function("window.scrollY > window.innerHeight * 0.6")
        assert page.locator("#campus-dashboard").count() == 1
        print("explore bridge verified", flush=True)

        page.evaluate("window.scrollTo(0, 0)")
        global_nav.get_by_role("button", name="我的课程").click()
        page.wait_for_url(f"{BASE_URL}/courses", timeout=10_000)
        print("dock bridge verified", flush=True)

        page.set_viewport_size({"width": 320, "height": 720})
        page.goto(f"{BASE_URL}/home", wait_until="networkidle", timeout=30_000)
        print("mobile page loaded", flush=True)
        mobile_iframe = page.locator(".sylva-home-hero iframe")
        mobile_scene = mobile_iframe.element_handle().content_frame()
        mobile_scene.wait_for_load_state("domcontentloaded")
        assert mobile_scene.query_selector("#scene") is not None
        mobile_box = page.locator(".sylva-home-hero").bounding_box()
        assert mobile_box and abs(mobile_box["width"] - 320) < 2
        assert mobile_box["height"] >= 560
        assert len(mobile_scene.query_selector_all(".dock [data-dock]")) == 5
        assert mobile_scene.query_selector(".dock-wrap").evaluate(
            "element => getComputedStyle(element).display"
        ) == "none"
        assert page.locator(".floating-nav").is_visible()
        assert page.locator(".floating-nav-button").count() == 8
        print("mobile scene verified", flush=True)

        assert not failed_local_assets, failed_local_assets
        assert not page_errors, page_errors
        browser.close()
        print("Sylva homepage smoke passed")


if __name__ == "__main__":
    run()
