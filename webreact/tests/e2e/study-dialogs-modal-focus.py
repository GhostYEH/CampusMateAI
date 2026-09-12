"""复盘弹窗 Modal 真实浏览器行为测试(Playwright)。

覆盖: 打开后 textarea 获焦 / 连续输入值完整且焦点不丢 /
Tab 与 Shift+Tab 不逃出弹窗 / Escape 关闭 / 点击遮罩关闭 /
关闭后焦点回到触发按钮 / body 滚动锁定与恢复。

运行前提: 后端(8000)与前端 dev(5174)已启动,API 全部 mock,不依赖真实登录态。
截图不落盘,只做行为断言,退出码 0=通过。
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5174")
TYPED = "专注复盘abc123"


def install_api_fakes(page):
    def handle(route):
        request = route.request
        url = request.url
        method = request.method
        if url.endswith("/health"):
            route.fulfill(status=200, content_type="application/json", body='{"ok":true}')
        elif url.endswith("/dashboard/student"):
            route.fulfill(status=200, content_type="application/json", body='{}')
        elif url.endswith("/study/sessions/active"):
            route.fulfill(status=200, content_type="application/json", body='null')
        elif url.endswith("/study/sessions") and method == "GET":
            route.fulfill(status=200, content_type="application/json", body='[]')
        elif url.endswith("/study/sessions") and method == "POST":
            route.fulfill(status=201, content_type="application/json", body='{"id":"study-1","status":"active","goal":"测试专注","started_at":"2026-09-12T00:00:00Z","planned_duration_seconds":1500,"pause_seconds":0}')
        elif url.endswith("/study/goals/daily") and method == "GET":
            route.fulfill(status=200, content_type="application/json", body='{"target_minutes":60,"updated_at":"2026-09-12T00:00:00Z"}')
        elif url.endswith("/tasks") and method == "GET":
            route.fulfill(status=200, content_type="application/json", body='[]')
        elif "/study/sessions/study-1/finish" in url:
            route.fulfill(status=200, content_type="application/json", body='{}')
        else:
            route.fulfill(status=200, content_type="application/json", body='{}')

    page.route("**/api/v1/**", handle)
    page.add_init_script("localStorage.setItem('campus_access_token', 'modal-focus-token'); localStorage.setItem('campus_session', JSON.stringify({role:'student', name:'验收同学'}));")


def check(condition, message, failures):
    print(("PASS " if condition else "FAIL ") + message)
    if not condition:
        failures.append(message)


def active_id(page):
    return page.evaluate("document.activeElement && document.activeElement.id || ''")


def modal_contains_focus(page):
    return page.evaluate("!!(document.querySelector('section.modal--study') && document.querySelector('section.modal--study').contains(document.activeElement))")


def run():
    failures = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        install_api_fakes(page)
        page.goto(f"{BASE}/study", wait_until="networkidle")
        page.locator(".study-summer-room").wait_for(timeout=15000)
        body_overflow_before = page.evaluate("document.body.style.overflow")
        html_overflow_before = page.evaluate("document.documentElement.style.overflow")
        gutter_before = page.evaluate("document.documentElement.style.scrollbarGutter")

        page.get_by_label("这次想完成什么").fill("测试专注")
        page.get_by_role("button", name="开始专注").click()
        page.get_by_role("button", name="暂停").wait_for(timeout=10000)
        trigger = page.get_by_role("button", name="结束并记录")
        trigger.wait_for()

        trigger.click()
        page.locator("section.modal--study").wait_for(timeout=5000)
        page.locator("#study-self-report").wait_for()
        page.wait_for_timeout(400)
        check(active_id(page) == "study-self-report", "打开复盘弹窗后 textarea 获得焦点", failures)
        check(page.evaluate("document.body.style.overflow") == "hidden", "弹窗打开时 body 锁定滚动", failures)
        check(page.evaluate("document.documentElement.style.overflow") == "hidden", "弹窗打开时 html 锁定滚动", failures)
        check(page.evaluate("document.documentElement.style.scrollbarGutter") == "auto", "弹窗打开时取消稳定滚动槽", failures)

        page.locator("#study-self-report").press_sequentially(TYPED, delay=15)
        check(page.locator("#study-self-report").input_value() == TYPED, "连续输入多个字符后值完整", failures)
        check(active_id(page) == "study-self-report", "输入多个字符后焦点仍在 textarea", failures)

        focusable_count = page.evaluate("document.querySelector('section.modal--study').querySelectorAll('button, [href], input, textarea, select, [tabindex]:not([tabindex=\"-1\"])').length")
        trapped = True
        for _ in range(focusable_count + 2):
            page.keyboard.press("Tab")
            if not modal_contains_focus(page):
                trapped = False
                break
        check(trapped, "Tab 不逃出弹窗", failures)
        trapped = True
        for _ in range(focusable_count + 2):
            page.keyboard.press("Shift+Tab")
            if not modal_contains_focus(page):
                trapped = False
                break
        check(trapped, "Shift+Tab 不逃出弹窗", failures)

        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        check(page.locator("section.modal--study").count() == 0, "Escape 关闭弹窗", failures)
        check("结束并记录" in page.evaluate("document.activeElement && document.activeElement.textContent || ''"), "Escape 关闭后焦点回到触发按钮", failures)
        check(page.evaluate("document.body.style.overflow") == body_overflow_before, "Escape 关闭后 body 滚动恢复原值", failures)
        check(page.evaluate("document.documentElement.style.overflow") == html_overflow_before, "Escape 关闭后 html 滚动恢复原值", failures)
        check(page.evaluate("document.documentElement.style.scrollbarGutter") == gutter_before, "Escape 关闭后滚动槽恢复原值", failures)

        trigger.click()
        page.locator("section.modal--study").wait_for(timeout=5000)
        page.locator("#study-self-report").wait_for()
        check(page.evaluate("document.body.style.overflow") == "hidden", "再次打开时 body 锁定滚动", failures)
        point = page.evaluate("""() => {
          const modal = document.querySelector('section.modal--study');
          const backdrop = document.querySelector('.modal-backdrop');
          if (!modal || !backdrop) return null;
          const rect = modal.getBoundingClientRect();
          const width = window.innerWidth;
          const height = window.innerHeight;
          const candidates = [
            [Math.floor(width / 2), Math.floor(rect.top / 2)],
            [Math.floor(width / 2), Math.floor((rect.bottom + height) / 2)],
            [Math.floor(rect.left / 2), Math.floor(height / 2)],
            [Math.floor((rect.right + width) / 2), Math.floor(height / 2)],
          ];
          for (const [x, y] of candidates) {
            if (x < 0 || y < 0 || x >= width || y >= height) continue;
            if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) continue;
            const el = document.elementFromPoint(x, y);
            if (el === backdrop) return {x, y};
          }
          return null;
        }""")
        check(point is not None, "找到遮罩可点击位置", failures)
        if point:
            page.mouse.click(point["x"], point["y"])
            page.wait_for_timeout(300)
        check(page.locator("section.modal--study").count() == 0, "点击遮罩关闭弹窗", failures)
        check("结束并记录" in page.evaluate("document.activeElement && document.activeElement.textContent || ''"), "遮罩关闭后焦点回到触发按钮", failures)
        check(page.evaluate("document.body.style.overflow") == body_overflow_before, "遮罩关闭后 body 滚动恢复原值", failures)
        check(page.evaluate("document.documentElement.style.overflow") == html_overflow_before, "遮罩关闭后 html 滚动恢复原值", failures)
        check(page.evaluate("document.documentElement.style.scrollbarGutter") == gutter_before, "遮罩关闭后滚动槽恢复原值", failures)

        check(not errors, "无页面异常", failures)
        if errors:
            print("pageerrors:", errors[:3])
        browser.close()

    if failures:
        print("\nFAILURES:")
        for item in failures:
            print(" -", item)
        return 1
    print("\nALL MODAL FOCUS CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(run())
