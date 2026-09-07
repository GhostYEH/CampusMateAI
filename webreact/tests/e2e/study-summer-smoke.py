from playwright.sync_api import sync_playwright


def install_api_fakes(page):
    def handle(route):
        request = route.request
        url = request.url
        if url.endswith("/health"):
            route.fulfill(status=200, content_type="application/json", body="{}")
        elif url.endswith("/study/sessions/active"):
            route.fulfill(status=200, content_type="application/json", body="null")
        elif url.endswith("/study/sessions") and request.method == "GET":
            route.fulfill(status=200, content_type="application/json", body="[]")
        elif url.endswith("/tasks"):
            route.fulfill(status=200, content_type="application/json", body="[]")
        elif url.endswith("/dashboard/student"):
            route.fulfill(status=200, content_type="application/json", body="{}")
        elif url.endswith("/study/sessions") and request.method == "POST":
            route.fulfill(status=201, content_type="application/json", body='{"id":"study-1","status":"active","goal":"测试专注","started_at":"2026-09-06T12:00:00Z","planned_duration_seconds":1500,"pause_seconds":0}')
        elif "/study/sessions/study-1/pause" in url:
            route.fulfill(status=200, content_type="application/json", body='{"id":"study-1","status":"paused","goal":"测试专注","started_at":"2026-09-06T12:00:00Z","planned_duration_seconds":1500,"pause_seconds":0}')
        else:
            route.fulfill(status=200, content_type="application/json", body="{}")

    page.route("**/api/v1/**", handle)
    page.add_init_script("localStorage.setItem('campus_access_token', 'smoke-token'); localStorage.setItem('campus_session', JSON.stringify({role:'student', name:'Smoke'}));")


def run():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        install_api_fakes(page)
        page.goto("http://127.0.0.1:5173/study")
        page.wait_for_load_state("networkidle")
        page.locator(".study-summer-room").wait_for()
        assert page.get_by_role("heading", name="学习陪伴").count() == 1
        assert page.get_by_role("button", name="选择学习场景").count() == 0
        page.get_by_role("button", name="雪景 安静一点").click()
        assert page.locator(".study-summer-room").get_attribute("data-study-scene") == "snow"
        page.get_by_label("这次想完成什么").fill("测试专注")
        page.get_by_role("button", name="开始专注").click()
        page.get_by_role("button", name="暂停").wait_for()
        page.get_by_role("button", name="暂停").click()
        page.get_by_role("button", name="继续").wait_for()

        mobile = browser.new_page(viewport={"width": 375, "height": 812})
        install_api_fakes(mobile)
        mobile.goto("http://127.0.0.1:5173/study")
        mobile.wait_for_load_state("networkidle")
        mobile.locator(".study-summer-room").wait_for()
        assert mobile.locator(".study-summer-dock").is_visible()
        browser.close()


if __name__ == "__main__":
    run()
