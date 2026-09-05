import json
import os

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5174")


def run():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("**/api/**", lambda route: route.fulfill(status=404, content_type="application/json", body='{"detail":"frontend smoke fixture"}'))
        token = os.environ.get("WEBREACT_SMOKE_TOKEN", "smoke")
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
        page.wait_for_selector(".login-panel-head h2", timeout=10000)
        page.evaluate(f"localStorage.setItem('campus_access_token', {json.dumps(token)}); localStorage.setItem('campus_session', JSON.stringify({{role: 'student', name: 'Test'}}));")

        page.goto(f"{BASE_URL}/home", wait_until="domcontentloaded")
        page.wait_for_selector("main h1")
        nav_geometry = page.locator(".floating-nav").evaluate("""nav => {
            const button = nav.querySelector('.floating-nav-button');
            const navRect = nav.getBoundingClientRect();
            const buttonRect = button?.getBoundingClientRect();
            return {
                width: navRect.width,
                height: navRect.height,
                buttonWidth: buttonRect?.width ?? 0,
                buttonHeight: buttonRect?.height ?? 0,
            };
        }""")
        assert nav_geometry["width"] >= 420
        assert nav_geometry["height"] >= 76
        assert nav_geometry["buttonWidth"] >= 44
        assert nav_geometry["buttonHeight"] >= 44

        home_button = page.get_by_role("button", name="首页")
        home_button.click()
        mouse_focus_shadow = home_button.evaluate(
            "button => getComputedStyle(button.closest('li')).boxShadow",
        )
        assert mouse_focus_shadow == "none"
        home_button.hover()
        page.wait_for_timeout(450)
        expanded_spacing = page.locator(".floating-nav-list").evaluate("""list => {
            const buttons = [...list.querySelectorAll('.floating-nav-button')]
                .map((button) => button.getBoundingClientRect());
            return {
                layoutGap: Number.parseFloat(getComputedStyle(list).columnGap),
                visualGaps: buttons.slice(1).map((button, index) => button.left - buttons[index].right),
            };
        }""")
        assert expanded_spacing["layoutGap"] >= 16
        assert min(expanded_spacing["visualGaps"]) >= 8
        indicator_geometry = home_button.evaluate("""button => {
            const indicator = button.querySelector('.floating-nav-icon');
            if (!indicator) return null;
            const icon = indicator.querySelector('svg');
            const indicatorRect = indicator.getBoundingClientRect();
            const iconRect = icon?.getBoundingClientRect();
            const buttonStyle = getComputedStyle(button);
            const oldFilterCircle = getComputedStyle(
                document.querySelector('.gooey-nav-effect.filter'),
                '::after',
            );
            return {
                width: indicatorRect.width,
                height: indicatorRect.height,
                centerOffsetX: iconRect ? Math.abs(
                    indicatorRect.left + indicatorRect.width / 2
                    - (iconRect.left + iconRect.width / 2)
                ) : Number.POSITIVE_INFINITY,
                centerOffsetY: iconRect ? Math.abs(
                    indicatorRect.top + indicatorRect.height / 2
                    - (iconRect.top + iconRect.height / 2)
                ) : Number.POSITIVE_INFINITY,
                buttonHeight: button.offsetHeight,
                buttonClipRadius: Number.parseFloat(buttonStyle.borderTopLeftRadius),
                radius: getComputedStyle(indicator, '::before').borderRadius,
                oldFilterContent: oldFilterCircle.content,
            };
        }""")
        assert indicator_geometry is not None, "active navigation icon needs its own indicator geometry"
        assert abs(indicator_geometry["width"] - indicator_geometry["height"]) < 0.5
        assert indicator_geometry["centerOffsetX"] < 0.5
        assert indicator_geometry["centerOffsetY"] < 0.5
        assert indicator_geometry["buttonClipRadius"] >= indicator_geometry["buttonHeight"] / 2
        assert indicator_geometry["radius"] == "50%"
        assert indicator_geometry["oldFilterContent"] == "none"

        page.goto(f"{BASE_URL}/tasks")
        page.wait_for_selector("main h1")
        page.wait_for_timeout(1000)
        page.get_by_role("button", name="新建待办").evaluate("(element) => element.click()")
        page.get_by_label("事项名称").fill("Playwright 回归任务")
        assert page.get_by_role("dialog").is_visible()
        page.get_by_role("button", name="取消").click()
        assert page.locator("[role=dialog]").count() == 0

        page.goto(f"{BASE_URL}/study")
        page.wait_for_selector("main h1")
        page.wait_for_timeout(1000)
        page.get_by_role("button", name="50 分钟").click()
        assert page.get_by_role("button", name="50 分钟").get_attribute("class") == "active"
        page.get_by_label("学习目标").fill("准备数据结构实验报告")
        assert page.get_by_role("button", name="让 AI 帮我拆解步骤").is_enabled()

        page.goto(f"{BASE_URL}/community/create")
        page.wait_for_selector("main h1")
        page.wait_for_timeout(1000)
        page.get_by_label("标题").fill("校园经验分享")
        page.get_by_role("button", name="预览").click()
        assert page.get_by_role("dialog").is_visible()
        page.get_by_role("button", name="继续编辑").click()
        assert page.locator("[role=dialog]").count() == 0

        page.set_viewport_size({"width": 320, "height": 720})
        page.goto(f"{BASE_URL}/home", wait_until="domcontentloaded")
        page.wait_for_selector("main h1")
        page.wait_for_timeout(500)
        assert page.locator(".floating-nav").count() == 1
        assert page.get_by_role("navigation", name="主导航").is_visible()
        assert not errors, errors
        browser.close()


if __name__ == "__main__":
    run()
