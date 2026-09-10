import json
import os

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5174")


def install_session_and_api_fixtures(page):
    dashboard = {
        "due_soon_assignments": [],
        "due_soon_personal_tasks": [],
        "pending_assignment_count": 0,
        "pending_personal_task_count": 0,
        "unread_announcement_count": 0,
        "enrolled_course_count": 0,
    }

    def handle(route):
        url = route.request.url
        if "/dashboard/student" in url:
            body = dashboard
        elif "/edu/schedule/items" in url:
            body = {"items": []}
        elif "/study/goals/daily" in url:
            body = {"target_minutes": 60, "updated_at": "2026-09-09T00:00:00Z"}
        elif "/study/checkins" in url:
            body = {"items": [], "total": 0, "streak": 0, "longest_streak": 0, "week_count": 0, "today_checked": False}
        elif "/study/sessions/active" in url:
            body = None
        elif "/study/sessions" in url:
            body = []
        else:
            body = {"items": []}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    page.route("**/api/v1/**", handle)
    page.add_init_script(
        """
        window.requestAnimationFrame = callback =>
          window.setTimeout(() => callback(performance.now()), 50);
        localStorage.setItem('campus_access_token', 'navigation-regression');
        localStorage.setItem('campus_session', JSON.stringify({role: 'student', name: '测试同学'}));
        localStorage.setItem('campus_dashboard_style', 'classic');
        """
    )


def rect(page, selector, index=0):
    value = page.evaluate(
        """({selector, index}) => {
          const element = document.querySelectorAll(selector)[index];
          if (!element) return null;
          const box = element.getBoundingClientRect();
          return {x: box.x, y: box.y, width: box.width, height: box.height};
        }""",
        {"selector": selector, "index": index},
    )
    assert value is not None
    return value


def surface_signature(page):
    return page.evaluate(
        """() => {
          const element = document.querySelector('.floating-nav');
          const style = getComputedStyle(element);
          return {
            backgroundColor: style.backgroundColor,
            borderColor: style.borderColor,
            boxShadow: style.boxShadow,
          };
        }"""
    )


def run():
    failures = []

    def expect(condition, message):
        if not condition:
            failures.append(message)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_default_timeout(10_000)
        shader_errors = []
        page.on(
            "console",
            lambda message: shader_errors.append(message.text)
            if message.type == "error" and "Liquid-metal" in message.text
            else None,
        )
        install_session_and_api_fixtures(page)

        print("opening home", flush=True)
        page.goto(f"{BASE_URL}/home", wait_until="domcontentloaded", timeout=30_000)
        print("home document loaded", flush=True)
        page.locator(".floating-nav").wait_for()
        print("home navigation visible", flush=True)
        page.mouse.move(20, 180)
        page.wait_for_timeout(900)

        account = rect(page, ".topbar-info-surface")
        search = rect(page, ".topbar-search-surface")
        expect(abs((account["x"] + account["width"]) - (1440 - 26)) < 1.5, "账户信息框没有固定在右侧 26px")
        expect(abs(search["x"] - 26) < 1.5, "搜索框没有固定在左侧 26px")

        nav = rect(page, ".floating-nav")
        stage_selector = ".floating-nav-list > li .sylva-liquid-stage--nav"
        stage_count = page.evaluate("selector => document.querySelectorAll(selector).length", stage_selector)
        first_stage = rect(page, stage_selector)
        last_stage = rect(page, stage_selector, stage_count - 1)
        left_gutter = first_stage["x"] - nav["x"]
        right_gutter = nav["x"] + nav["width"] - last_stage["x"] - last_stage["width"]
        expect(abs(left_gutter - right_gutter) < 1.5, f"导航左右留白不一致：{left_gutter:.1f}px / {right_gutter:.1f}px")

        active_selector = ".floating-nav-list > li.active .sylva-liquid-stage--nav"
        stage_box = rect(page, active_selector)
        icon_box = rect(page, f"{active_selector} .floating-nav-icon")
        stage_center = stage_box["x"] + stage_box["width"] / 2
        icon_center = icon_box["x"] + icon_box["width"] / 2
        expect(abs(stage_center - icon_center) < 0.75, f"当前页面图标与特效圆心相差 {stage_center - icon_center:.1f}px")

        home_surface = surface_signature(page)
        compact_nav_width = nav["width"]
        task_selector = '.floating-nav-button[aria-label="待办与作业"]'
        for _ in range(3):
            task_box = rect(page, task_selector)
            page.mouse.move(task_box["x"] + task_box["width"] / 2, task_box["y"] + task_box["height"] / 2)
            page.wait_for_timeout(350)
        print("task navigation hovered", flush=True)
        page.wait_for_timeout(900)
        task_state = page.evaluate(
            """selector => {
              const stage = document.querySelector(selector)?.closest('.sylva-liquid-stage');
              const canvas = stage.querySelector('canvas');
              const gl = canvas?.getContext('webgl2');
              return {
                hot: stage.classList.contains('hot'),
                fallback: stage.classList.contains('sylva-liquid-fallback'),
                hasCanvas: Boolean(canvas),
                contextLost: gl ? gl.isContextLost() : null,
              };
            }""",
            task_selector,
        )
        expect(task_state["hot"], "待办与作业没有进入指针悬停状态")
        expect(task_state["hasCanvas"], "待办与作业没有创建液态金属画布")
        expect(not task_state["fallback"], "待办与作业退化成静态 CSS 效果")
        expect(task_state["contextLost"] is False, "待办与作业的 WebGL 上下文已丢失")
        hovered_nav = rect(page, ".floating-nav")
        task_label = rect(page, f'{task_selector} .floating-nav-label')
        expect(hovered_nav["width"] > compact_nav_width + 200, "指针悬停后导航没有展开")
        expect(task_label["width"] > 40, "指针悬停后没有显示待办与作业的详细名称")
        expect(not shader_errors, f"液态金属着色器报错：{shader_errors}")

        page.goto(f"{BASE_URL}/tasks", wait_until="domcontentloaded", timeout=30_000)
        page.locator(".floating-nav").wait_for()
        page.wait_for_timeout(700)
        task_active = page.evaluate(
            """() => {
              const button = document.querySelector('.floating-nav-button[aria-label="待办与作业"]');
              const stage = button?.closest('.sylva-liquid-stage--nav');
              return {current: button?.getAttribute('aria-current'), active: stage?.dataset.active};
            }"""
        )
        expect(task_active == {"current": "page", "active": "true"}, "待办页没有保持统一的液态金属活动态")

        print("opening study", flush=True)
        page.goto(f"{BASE_URL}/study", wait_until="domcontentloaded", timeout=30_000)
        print("study document loaded", flush=True)
        page.locator(".floating-nav").wait_for()
        page.mouse.move(20, 180)
        page.wait_for_timeout(900)
        study_surface = surface_signature(page)
        expect(study_surface == home_surface, f"学习页替换了导航材质：{home_surface} -> {study_surface}")
        study_stage_count = page.evaluate("selector => document.querySelectorAll(selector).length", active_selector)
        expect(study_stage_count == 1, "学习页没有沿用统一的液态金属活动项")

        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.set_default_timeout(10_000)
        install_session_and_api_fixtures(mobile)
        mobile.goto(f"{BASE_URL}/home", wait_until="domcontentloaded", timeout=30_000)
        mobile.locator(".floating-nav").wait_for()
        mobile.wait_for_timeout(500)
        mobile_nav = rect(mobile, ".floating-nav")
        expect(abs(mobile_nav["width"] - 366) < 1.5, f"移动端导航宽度异常：{mobile_nav['width']:.1f}px")
        expect(abs((mobile_nav["y"] + mobile_nav["height"]) - (844 - 15)) < 1.5, "移动端导航没有固定在底部安全距离")
        mobile.close()

        browser.close()

    if failures:
        raise AssertionError("\n".join(f"- {failure}" for failure in failures))


if __name__ == "__main__":
    run()
