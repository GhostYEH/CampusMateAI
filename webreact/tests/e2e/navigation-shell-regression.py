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
        localStorage.setItem('campus_access_token', 'navigation-regression');
        localStorage.setItem('campus_session', JSON.stringify({role: 'student', name: '测试同学'}));
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


def rects(page, selector):
    return page.evaluate(
        """selector => Array.from(document.querySelectorAll(selector), element => {
          const box = element.getBoundingClientRect();
          return {x: box.x, y: box.y, width: box.width, height: box.height};
        })""",
        selector,
    )


def surface_signature(page):
    return page.evaluate(
        """() => {
          const element = document.querySelector('.floating-nav-list > li:not(.active) .sylva-liquid-plate');
          const style = getComputedStyle(element);
          return {
            backgroundColor: style.backgroundColor,
            backgroundImage: style.backgroundImage,
            borderRadius: style.borderRadius,
            boxShadow: style.boxShadow,
            opacity: style.opacity,
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
        install_session_and_api_fixtures(page)
        print("desktop: open home", flush=True)
        page.goto(f"{BASE_URL}/home", wait_until="domcontentloaded", timeout=30_000)
        page.locator(".floating-nav").wait_for()
        page.evaluate("() => document.fonts.ready")
        page.wait_for_timeout(400)

        account = rect(page, ".topbar-info-surface")
        search = rect(page, ".topbar-search-surface")
        root_box = rect(page, "html")
        nav = rect(page, ".floating-nav")
        expect(abs(search["x"] - 26) < 1.5, "搜索框没有固定在左侧 26px")
        expect(abs((account["x"] + account["width"]) - (root_box["x"] + root_box["width"] - 26)) < 1.5, "账户信息框没有固定在右侧 26px")
        expect(abs(nav["y"] - 14) < 1.5, "1440px 导航没有固定在顶部")
        expect(search["x"] + search["width"] <= nav["x"], "1440px 导航与搜索框重叠")
        expect(nav["x"] + nav["width"] <= account["x"], "1440px 导航与账户区重叠")

        stage_selector = ".floating-nav-list > li .sylva-liquid-stage--nav"
        before = rects(page, stage_selector)
        labels = page.locator(".floating-nav-label")
        nav_state = page.evaluate(
            """() => ({
              innerWidth,
              markup: document.querySelector('.floating-nav-inner')?.outerHTML.slice(0, 260),
              labels: Array.from(document.querySelectorAll('.floating-nav-label'), label => ({
                display: getComputedStyle(label).display,
                width: label.getBoundingClientRect().width,
              })),
            })"""
        )
        expect(len(before) == 9, f"导航按钮数量应为 9，实际为 {len(before)}")
        expect(labels.count() == 9, f"导航文字数量应为 9，实际为 {labels.count()}")
        expect(all(label.is_visible() for label in labels.all()), f"桌面导航文字没有全部稳定显示：{nav_state}")
        expect(all(abs(box["height"] - 44) < 0.1 for box in before), f"桌面按钮高度不统一：{before}")
        expect(page.locator('.floating-nav-inner[data-static-controls="true"]').count() == 1, f"全局导航没有启用稳定控件模式：{nav_state}")
        expect(page.locator(".floating-nav canvas").count() == 0, "全局导航仍然挂载会闪烁的液态画布")
        print("desktop: initial layout sampled", flush=True)

        first_stage = before[0]
        last_stage = before[-1]
        left_gutter = first_stage["x"] - nav["x"]
        right_gutter = nav["x"] + nav["width"] - last_stage["x"] - last_stage["width"]
        expect(abs(left_gutter - right_gutter) < 1.5, f"导航左右留白不一致：{left_gutter:.1f}px / {right_gutter:.1f}px")

        task_box = rect(page, '.floating-nav-button[aria-label="待办与作业"]')
        page.mouse.move(task_box["x"] + task_box["width"] / 2, task_box["y"] + task_box["height"] / 2)
        page.wait_for_timeout(500)
        print("desktop: hover sampled", flush=True)
        after = rects(page, stage_selector)
        stable = all(
            all(abs(left[key] - right[key]) < 0.25 for key in ("x", "y", "width", "height"))
            for left, right in zip(before, after)
        )
        expect(stable, f"悬停导致导航尺寸或位置变化：{before} -> {after}")
        expect(page.locator(".floating-nav canvas").count() == 0, "悬停后导航重新挂载了液态画布")
        screenshot_path = os.environ.get("NAV_SCREENSHOT_PATH")
        if screenshot_path:
            page.screenshot(
                path=screenshot_path,
                clip={"x": 0, "y": 0, "width": 1440, "height": 96},
                animations="disabled",
                timeout=30_000,
            )

        home_surface = surface_signature(page)
        print("routes: open tasks", flush=True)
        page.goto(f"{BASE_URL}/tasks", wait_until="domcontentloaded", timeout=30_000)
        page.locator(".floating-nav").wait_for()
        expect(page.locator('.floating-nav-button[aria-label="待办与作业"][aria-current="page"]').count() == 1, "待办页活动项不正确")
        expect(page.locator(".floating-nav canvas").count() == 0, "路由切换后导航重新挂载了液态画布")

        print("routes: open study", flush=True)
        page.goto(f"{BASE_URL}/study", wait_until="domcontentloaded", timeout=30_000)
        page.locator(".floating-nav").wait_for()
        page.wait_for_timeout(250)
        expect(surface_signature(page) == home_surface, "不同页面的导航材质不一致")

        print("responsive: compact", flush=True)
        page.set_viewport_size({"width": 1439, "height": 900})
        page.wait_for_timeout(250)
        compact_nav = rect(page, ".floating-nav")
        compact_study_dock = rect(page, ".study-summer-dock")
        expect(abs((compact_nav["y"] + compact_nav["height"]) - (900 - 15)) < 1.5, "1439px 导航没有切换到底部")
        expect(compact_study_dock["y"] + compact_study_dock["height"] <= compact_nav["y"] - 8, "1439px 学习二级导航与全局导航重叠")
        expect(page.locator(".floating-nav-label:visible").count() == 0, "底部紧凑导航仍显示文字")
        expect(page.locator(".floating-nav canvas").count() == 0, "响应式切换时导航挂载了液态画布")

        print("responsive: desktop", flush=True)
        page.set_viewport_size({"width": 1440, "height": 900})
        page.wait_for_timeout(250)
        restored_nav = rect(page, ".floating-nav")
        expect(abs(restored_nav["y"] - 14) < 1.5, "恢复桌面宽度后导航没有回到顶部")
        expect(page.locator(".floating-nav-label:visible").count() == 9, "恢复桌面宽度后文字没有全部显示")
        expect(page.locator(".floating-nav canvas").count() == 0, "恢复桌面宽度时导航挂载了液态画布")

        print("responsive: mobile", flush=True)
        mobile = browser.new_page(viewport={"width": 320, "height": 780})
        mobile.set_default_timeout(10_000)
        install_session_and_api_fixtures(mobile)
        mobile.goto(f"{BASE_URL}/home", wait_until="domcontentloaded", timeout=30_000)
        mobile.locator(".floating-nav").wait_for()
        mobile.wait_for_timeout(250)
        mobile_nav = rect(mobile, ".floating-nav")
        expect(abs(mobile_nav["width"] - 296) < 1.5, f"移动端导航宽度异常：{mobile_nav['width']:.1f}px")
        expect(abs((mobile_nav["y"] + mobile_nav["height"]) - (780 - 15)) < 1.5, "移动端导航没有固定在底部安全距离")
        expect(mobile.locator(".floating-nav canvas").count() == 0, "移动端导航挂载了液态画布")
        mobile.goto(f"{BASE_URL}/study", wait_until="domcontentloaded", timeout=30_000)
        mobile.locator(".study-summer-dock").wait_for()
        mobile_study_nav = rect(mobile, ".floating-nav")
        mobile_study_dock = rect(mobile, ".study-summer-dock")
        expect(abs((mobile_study_nav["y"] + mobile_study_nav["height"]) - (780 - 15)) < 1.5, "学习页移动端全局导航没有保持在底部")
        expect(mobile_study_dock["y"] + mobile_study_dock["height"] <= mobile_study_nav["y"] - 8, "学习页移动端两层导航重叠")
        mobile.close()
        browser.close()

    if failures:
        raise AssertionError("\n".join(f"- {failure}" for failure in failures))


if __name__ == "__main__":
    run()
