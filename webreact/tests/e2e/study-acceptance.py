"""学习陪伴迁移验收脚本：三端尺寸截图 + 核心页面断言。

运行前提：8000 后端与 5174 前端已启动。截图保存到 tests/e2e/shots/。
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5174"
OUT = Path(__file__).resolve().parent / "shots"
OUT.mkdir(parents=True, exist_ok=True)

VIEWPORTS = [
    (2552, 1308, "wide"),
    (1440, 900, "desktop"),
    (390, 844, "mobile"),
]

PAGES = [
    ("/study", "study"),
    ("/plans", "plans"),
    ("/statistics", "statistics"),
]


def main() -> int:
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # 登录（真实 API）
        api = p.request.new_context()
        auth = api.post(
            f"{BASE}/api/v1/auth/login",
            data=json.dumps({"username": "student_demo", "password": "Demo123456"}),
            headers={"Content-Type": "application/json"},
        )
        token = auth.json()["access_token"]
        api.dispose()

        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        # 真实 UI 登录（与应用行为一致，走 auth/login + /auth/me）
        page.goto(f"{BASE}/login", wait_until="networkidle")
        page.locator('form input').nth(0).fill("student_demo")
        page.locator('form input').nth(1).fill("Demo123456")
        page.locator('form button:has-text("登录")').click()
        page.wait_for_url(f"{BASE}/home", timeout=15000)
        page.wait_for_timeout(600)

        for width, height, label in VIEWPORTS:
            page.set_viewport_size({"width": width, "height": height})
            for route, name in PAGES:
                page.goto(f"{BASE}{route}", wait_until="networkidle")
                page.wait_for_timeout(700)
                shot = OUT / f"{name}-{label}-{width}x{height}.png"
                page.screenshot(path=str(shot), full_page=False)
                flagged = []
                # 无横向溢出
                overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
                if overflow:
                    flagged.append("horizontal-overflow")
                # /study: 房间无边框盒子、三栏、双导航不重叠
                if route == "/study":
                    room = page.evaluate("""() => {
                      const el = document.querySelector('.study-summer-room');
                      if (!el) return null;
                      const s = getComputedStyle(el);
                      return { borderWidth: s.borderWidth, radius: s.borderRadius,
                               bg: s.backgroundColor, grid: getComputedStyle(document.querySelector('.study-summer-grid')).gridTemplateColumns };
                    }""")
                    if room is None or room["borderWidth"] != "0px" or room["radius"] != "0px" or room["bg"] != "rgba(0, 0, 0, 0)":
                        flagged.append("room-not-borderless")
                    cols = [float(x.replace("px", "")) for x in room["grid"].split()] if room and room["grid"] else []
                    if len(cols) >= 3 and cols[2] < 200:
                        flagged.append("right-column-too-narrow")
                    dock = page.locator(".study-summer-dock")
                    nav = page.locator(".floating-nav")
                    if not dock.is_visible():
                        flagged.append("dock-missing")
                    else:
                        db = dock.bounding_box()
                        nb = nav.bounding_box()
                        if db and nb and db["y"] < nb["y"] + nb["height"]:
                            flagged.append("nav-overlap")
                # 页面顶部无错误横幅
                err = page.locator(".notice-error").count()
                if err:
                    flagged.append("error-banner")
                print(f"shot {name}-{label}: {shot.name} {('FLAG ' + ','.join(flagged)) if flagged else 'OK'}")
                if flagged:
                    failures.append(f"{name}-{label}: {','.join(flagged)}")

        # /plans AI 拆解真实流程
        page.set_viewport_size({"width": 1440, "height": 900})
        page.goto(f"{BASE}/study", wait_until="networkidle")
        page.wait_for_timeout(500)
        # 即使已有进行中的专注会话，右侧入口也应能打开拆解台。
        page.get_by_role("button", name="用 AI 拆解学习目标").click()
        page.locator(".study-summer-breakdown").wait_for()
        page.locator(".study-summer-breakdown__input textarea").fill("复习线性代数第一章并完成课后习题")
        page.locator(".study-summer-breakdown__input .button").click()
        page.wait_for_function(
            "() => document.querySelector('.study-summer-breakdown__step') || "
            "document.querySelector('.notice-error') || "
            "!document.querySelector('.study-summer-breakdown__input .button:disabled')",
            timeout=35000,
        )
        page.wait_for_timeout(500)
        focus_step_count = page.locator(".study-summer-breakdown__step").count()
        print(f"study focus ai steps after generate: {focus_step_count}")
        if focus_step_count == 0:
            failures.append("study: no in-place AI breakdown steps generated")
        else:
            page.locator(".study-summer-breakdown__footer .button").click()
            page.wait_for_timeout(1200)
            if page.locator(".study-summer-breakdown").count():
                failures.append("study: saving breakdown steps did not close the panel")

        # /plans AI 拆解真实流程
        page.goto(f"{BASE}/plans?ai=1", wait_until="networkidle")
        page.wait_for_timeout(500)
        if page.locator(".study-ai-planner").count() == 0:
            failures.append("plans: ai-planner did not auto-open on ?ai=1")
        page.locator(".study-ai-planner__input textarea").fill("复习高等数学第一章并完成课后习题")
        page.locator(".study-ai-planner__input .button").click()
        # 轮询等待生成完成（后端真实 LLM 调用，允许 30s）
        page.wait_for_function(
            "() => document.querySelector('.study-ai-step') || "
            "document.querySelector('.notice-error') || "
            "!document.querySelector('.study-ai-planner__input .button:disabled')",
            timeout=35000,
        )
        page.wait_for_timeout(1200)
        step_count = page.locator(".study-ai-step").count()
        print(f"plans ai steps after generate: {step_count}")
        err_banner = page.locator(".notice-error").count()
        if err_banner:
            print("plans ai error banner:", page.locator(".notice-error").first.text_content())
        if step_count == 0:
            page.screenshot(path=str(OUT / "plans-ai-generated.png"))
            failures.append(f"plans: no steps generated (err_banner={err_banner})")
        else:
            # 编辑第一步标题 + 删除第二步
            page.locator(".study-ai-step input").first.fill("第一步：通读教材定义")
            if step_count >= 2:
                page.locator(".study-ai-step__remove").nth(1).click()
            page.screenshot(path=str(OUT / "plans-ai-edited.png"))
            page.locator(".study-ai-planner__save .button").click()
            page.wait_for_timeout(2500)
            row_count = page.locator(".study-plan-row").count()
            print(f"plans rows after save: {row_count}")
            if row_count == 0:
                failures.append("plans: save produced no rows")

        page.goto(f"{BASE}/statistics", wait_until="networkidle")
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "statistics-desktop-1440x900.png"))
        errs = page.locator(".notice-error").count()
        if errs:
            failures.append("statistics: error banner present")

        # 控制台异常与 5xx 网络检查
        console_errors = []
        page.goto(f"{BASE}/study", wait_until="networkidle")
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.goto(f"{BASE}/study", wait_until="networkidle")
        page.wait_for_timeout(800)
        # 通过 CDP 拿 performance 里的失败请求
        failed_requests = page.evaluate("""() => performance.getEntriesByType('resource')
            .filter(e => e.name.includes('/api/') && e.duration === 0).map(e => e.name)""")
        print("console errors:", console_errors[:5] if console_errors else "none")
        print("failed api resources:", failed_requests[:5] if failed_requests else "none")

        browser.close()

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(" -", f)
        return 1
    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
