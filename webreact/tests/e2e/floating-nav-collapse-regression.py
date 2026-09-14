import json
import os

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5174")


def install_fixtures(page):
    page.route(
        "**/api/v1/**",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"items": []}),
        ),
    )
    page.add_init_script(
        """
        window.requestAnimationFrame = callback =>
          window.setTimeout(() => callback(performance.now()), 50);
        localStorage.setItem('campus_access_token', 'floating-nav-collapse-regression');
        localStorage.setItem('campus_session', JSON.stringify({role: 'student', name: '测试同学'}));
        """
    )


def run():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": int(os.environ.get("WEB_VIEWPORT_WIDTH", "1440")), "height": 900})
        page.set_default_timeout(10_000)
        install_fixtures(page)

        page.goto(f"{BASE_URL}/home", wait_until="networkidle", timeout=30_000)
        page.locator(".floating-nav").wait_for()
        page.mouse.move(1400, 880)
        page.wait_for_timeout(500)

        collapsed = page.locator(".floating-nav").evaluate(
            """nav => {
              const navRect = nav.getBoundingClientRect();
              const stages = [...nav.querySelectorAll('.sylva-liquid-stage--nav')]
                .map(stage => stage.getBoundingClientRect());
              return {
                clientWidth: nav.clientWidth,
                scrollWidth: nav.scrollWidth,
                leftInset: stages[0].left - navRect.left,
                rightInset: navRect.right - stages.at(-1).right,
              };
            }"""
        )
        task_box = page.get_by_role("button", name="待办与作业", exact=True).bounding_box()
        assert task_box is not None
        page.mouse.move(task_box["x"] + task_box["width"] / 2, task_box["y"] + task_box["height"] / 2)
        page.wait_for_timeout(500)
        home_box = page.get_by_role("button", name="首页", exact=True).bounding_box()
        assert home_box is not None
        page.mouse.move(home_box["x"] + home_box["width"] / 2, home_box["y"] + home_box["height"] / 2)
        page.get_by_role("button", name="首页", exact=True).focus()
        page.wait_for_timeout(300)
        expanded = page.locator(".floating-nav").evaluate(
            """nav => {
              const navRect = nav.getBoundingClientRect();
              const stages = [...nav.querySelectorAll('.sylva-liquid-stage--nav')]
                .map(stage => stage.getBoundingClientRect());
              return {
                width: navRect.width,
                clientWidth: nav.clientWidth,
                scrollWidth: nav.scrollWidth,
                firstStageInset: stages[0].left - navRect.left,
                lastStageInset: navRect.right - stages.at(-1).right,
              };
            }"""
        )
        expanded_effect = page.locator(".floating-nav").evaluate(
            """nav => {
              const stage = nav.querySelector('.floating-nav-list > li.active .sylva-liquid-stage--nav');
              const canvasBox = stage?.querySelector('.sylva-liquid-fx')?.getBoundingClientRect();
              const iconBox = stage?.querySelector('.floating-nav-icon')?.getBoundingClientRect();
              if (!canvasBox || !iconBox) return null;
              return {
                horizontalPadding: canvasBox.width - iconBox.width,
                verticalPadding: canvasBox.height - iconBox.height,
              };
            }"""
        )
        page.locator(".floating-nav").evaluate(
            """nav => {
              window.__floatingNavCollapseStart = null;
              nav.addEventListener('pointerleave', () => queueMicrotask(() => {
                const activeStage = nav.querySelector('.floating-nav-list > li.active .sylva-liquid-stage--nav');
                const icon = activeStage?.querySelector('.floating-nav-icon');
                const plate = activeStage?.querySelector('.sylva-liquid-plate');
                const iconBox = icon?.getBoundingClientRect();
                window.__floatingNavCollapseStart = {
                  iconWidth: iconBox?.width ?? 0,
                  plateOpacity: plate ? getComputedStyle(plate).opacity : null,
                };
              }), {once: true});
            }"""
        )
        page.mouse.move(1400, 880)
        page.wait_for_timeout(100)
        collapse_start = page.evaluate("() => window.__floatingNavCollapseStart")
        failures = []
        if collapsed["scrollWidth"] > collapsed["clientWidth"] + 1:
            failures.append(f"收起态内容溢出：{collapsed}")
        if collapsed["leftInset"] < -1 or collapsed["rightInset"] < -1:
            failures.append(f"收起态入口超出容器：{collapsed}")
        if expanded["width"] < collapsed["clientWidth"] + 200:
            failures.append(f"导航未正常展开：{expanded}")
        if expanded["scrollWidth"] > expanded["clientWidth"] + 1:
            failures.append(f"展开态内容溢出：{expanded}")
        if expanded["firstStageInset"] < 14 or expanded["lastStageInset"] < 14:
            failures.append(f"展开态首尾留白不足：{expanded}")
        if expanded_effect and abs(expanded_effect["horizontalPadding"] - expanded_effect["verticalPadding"]) >= 1:
            failures.append(f"液态画布未固定到选中图标：{expanded_effect}")
        if not collapse_start:
            failures.append("未捕获导航收缩起始帧")
        elif collapse_start["iconWidth"] > 44.5:
            failures.append(f"收缩开始时选中图标意外放大：{collapse_start}")
        if collapse_start and collapse_start["plateOpacity"] != "1":
            failures.append(f"收缩开始时选中底板透明度闪动：{collapse_start}")

        assert not failures, "\n".join(failures)

        browser.close()


if __name__ == "__main__":
    run()
