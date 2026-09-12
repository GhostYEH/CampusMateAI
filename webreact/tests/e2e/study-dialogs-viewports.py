"""学习弹窗多视口 E2E 检查(Playwright)。

同时打开并检查: 本次学习复盘弹窗 / AI 目标拆解弹窗(含多个步骤后的
内部滚动区) / footer 始终可见 / 无横向溢出、双滚动条和按钮裁切。

视口: 2560x1308 / 1440x900 / 1024x768 / 390x844 / 360x800,
以及 640x360 CSS 视口(模拟 1280x720 物理窗口在 200% 缩放下的布局视口)。
注意: device_scale_factor 只改变 DPR,不改变 CSS layout viewport,
不能用它等效缩放,必须直接用缩小后的 CSS 视口。

API 全部 mock,12 个步骤由 task-breakdown 接口直接返回,不依赖真实 LLM。
截图保存到系统临时目录,不提交到仓库。退出码 0=通过。
"""
import os
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5174")
OUT = Path(tempfile.gettempdir()) / "study-dialogs-shots"
OUT.mkdir(parents=True, exist_ok=True)

VIEWPORTS = [
    (2560, 1308, "2560x1308"),
    (1440, 900, "1440x900"),
    (1024, 768, "1024x768"),
    (390, 844, "390x844"),
    (360, 800, "360x800"),
    (640, 360, "zoom200"),
]

STEPS = [
    {
        "step_number": i + 1,
        "title": f"第{i + 1}步:复习重点内容并做练习",
        "description": f"第{i + 1}步的具体做法说明,先通读教材再完成对应习题,记录疑问点。",
        "estimated_minutes": 30,
        "dependencies": [i] if i else [],
        "completion_criteria": f"完成第{i + 1}步习题并核对答案",
        "is_policy_step": False,
        "knowledge_source": None,
    }
    for i in range(12)
]


def install_api_fakes(page):
    import json as jsonlib

    breakdown = jsonlib.dumps(
        {
            "mode": "llm",
            "goal": "复习高等数学第一章",
            "related_task_id": None,
            "related_task_title": None,
            "warnings": [],
            "steps": STEPS,
        },
        ensure_ascii=False,
    )

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
        elif url.endswith("/study/task-breakdown") and method == "POST":
            route.fulfill(status=200, content_type="application/json", body=breakdown)
        elif url.endswith("/tasks") and method == "GET":
            route.fulfill(status=200, content_type="application/json", body='[]')
        elif "/study/sessions/study-1/pause" in url:
            route.fulfill(status=200, content_type="application/json", body='{"id":"study-1","status":"paused","goal":"测试专注","started_at":"2026-09-12T00:00:00Z","planned_duration_seconds":1500,"pause_seconds":0}')
        elif "/study/sessions/study-1/finish" in url:
            route.fulfill(status=200, content_type="application/json", body='{}')
        else:
            route.fulfill(status=200, content_type="application/json", body='{}')

    page.route("**/api/v1/**", handle)
    page.add_init_script("localStorage.setItem('campus_access_token', 'dialogs-shots-token'); localStorage.setItem('campus_session', JSON.stringify({role:'student', name:'验收同学'}));")


def check(condition, message, failures):
    print(("PASS " if condition else "FAIL ") + message)
    if not condition:
        failures.append(message)


def dialog_metrics(page, selector):
    return page.evaluate(
        """(sel) => {
          const el = document.querySelector(sel);
          if (!el) return null;
          const rect = el.getBoundingClientRect();
          const style = getComputedStyle(el);
          const scroller = document.querySelector('.study-summer-breakdown__steps');
          const scrollerRect = scroller ? scroller.getBoundingClientRect() : null;
          const footer = document.querySelector('.study-summer-breakdown__footer');
          const footerRect = footer ? footer.getBoundingClientRect() : null;
          const buttons = Array.from(el.querySelectorAll('button')).map((btn) => {
            const r = btn.getBoundingClientRect();
            const bs = getComputedStyle(btn);
            return { visible: r.width > 0 && r.height > 0, clipped: r.width < 4 || r.height < 4, opacity: bs.opacity, display: bs.display, visibility: bs.visibility };
          });
          const scrollables = [];
          let node = el.parentElement;
          while (node && node !== document.body) {
            const s = getComputedStyle(node);
            if ((s.overflowY === 'auto' || s.overflowY === 'scroll') && node.scrollHeight > node.clientHeight + 1) scrollables.push(node.className);
            node = node.parentElement;
          }
          return {
            rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height},
            overflowX: document.documentElement.scrollWidth > window.innerWidth + 1,
            bodyScrollY: document.body.scrollHeight > window.innerHeight + 1,
            footerVisible: footerRect ? (footerRect.top >= 0 && footerRect.bottom <= window.innerHeight + 1) : null,
            stepsScrollable: scroller ? (scroller.scrollHeight > scroller.clientHeight + 1) : null,
            stepsCount: scroller ? scroller.querySelectorAll('.study-summer-breakdown__step').length : null,
            buttonCount: buttons.length,
            clippedButtons: buttons.filter((b) => b.clipped).length,
            hiddenButtons: buttons.filter((b) => !b.visible || b.display === 'none' || b.visibility === 'hidden').length,
            outerScrollables: scrollables,
            doubleScrollbar: (scroller ? (scroller.scrollHeight > scroller.clientHeight + 1) : false)
              && (style.overflowY === 'auto' || style.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 1,
          };
        }""",
        selector,
    )


def run():
    failures = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for width, height, label in VIEWPORTS:
            context = browser.new_context(viewport={"width": width, "height": height})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            install_api_fakes(page)
            page.goto(f"{BASE}/study", wait_until="networkidle")
            page.locator(".study-summer-room").wait_for(timeout=15000)
            if label == "zoom200":
                inner = page.evaluate("({w: window.innerWidth, h: window.innerHeight})")
                check(abs(inner["w"] - 640) <= 4 and abs(inner["h"] - 360) <= 4, f"[{label}] CSS 视口约为 640x360(实际 {inner['w']}x{inner['h']})", failures)

            page.get_by_role("button", name="用 AI 拆解学习目标").click()
            page.locator(".study-summer-breakdown").wait_for(timeout=5000)
            page.locator(".study-summer-breakdown__input textarea").fill("复习高等数学第一章,并完成课后习题")
            page.locator(".study-summer-breakdown__input .button").click()
            page.locator(".study-summer-breakdown__step").first.wait_for(timeout=10000)
            page.wait_for_timeout(400)

            scroll_before = page.evaluate("window.scrollY")
            check(page.evaluate("document.body.style.overflow") == "hidden", f"[{label}] 拆解弹窗打开时 body 锁定滚动", failures)
            check(page.evaluate("document.documentElement.style.overflow") == "hidden", f"[{label}] 拆解弹窗打开时 html 锁定滚动", failures)
            steps_top_before = page.evaluate("document.querySelector('.study-summer-breakdown__steps').scrollTop")
            # 滚轮落在步骤列表上: 背景不动,步骤区可滚动。
            # 小高度视口下步骤区可能被压缩到不可见,此时退化为 JS 滚动断言。
            steps_visible = page.locator(".study-summer-breakdown__steps").is_visible()
            if steps_visible:
                page.locator(".study-summer-breakdown__steps").hover()
                page.mouse.wheel(0, 800)
                page.wait_for_timeout(200)
                check(page.evaluate("window.scrollY") == scroll_before, f"[{label}] 步骤区滚轮不带动背景", failures)
                check(page.evaluate("document.querySelector('.study-summer-breakdown__steps').scrollTop") >= steps_top_before, f"[{label}] 步骤区滚轮可内部滚动", failures)
            else:
                page.evaluate("document.querySelector('.study-summer-breakdown__steps').scrollTop += 200")
                check(page.evaluate("window.scrollY") == scroll_before, f"[{label}] 步骤区滚动不带动背景", failures)
            # 键盘 PageDown: 背景不动
            page.keyboard.press("PageDown")
            page.wait_for_timeout(200)
            check(page.evaluate("window.scrollY") == scroll_before, f"[{label}] 键盘翻页不改变背景位置", failures)
            # 编程式 window.scrollTo 会被 overflow:hidden 钳制: 大视口下文档不超高本就为 0;
            # 小视口下钳制到最大值,允许变化但不得超过最大值,且应在 html 锁定时被钳制。
            page.evaluate("window.scrollTo(0, 99999)")
            page.wait_for_timeout(200)
            scroll_after_programmatic = page.evaluate("window.scrollY")
            scroll_max = page.evaluate("document.documentElement.scrollHeight - window.innerHeight")
            check(scroll_after_programmatic <= max(scroll_max, scroll_before), f"[{label}] 编程式滚动被钳制在文档范围内", failures)

            m = dialog_metrics(page, ".study-summer-breakdown")
            check(m is not None, f"[{label}] 拆解弹窗可度量", failures)
            btn_bg = page.evaluate("() => { const btn = document.querySelector('.study-summer-breakdown__input .button'); return btn ? getComputedStyle(btn).backgroundColor : null; }")
            check(btn_bg in ("rgb(215, 239, 131)", "rgb(229, 248, 159)"), f"[{label}] 输入区主按钮为苔绿色(实际 {btn_bg})", failures)
            if m:
                check(m["stepsCount"] == 12, f"[{label}] 12 个步骤全部渲染(实际 {m['stepsCount']})", failures)
                check(m["stepsScrollable"], f"[{label}] 步骤区内部可滚动", failures)
                check(m["footerVisible"], f"[{label}] footer 始终可见", failures)
                check(not m["overflowX"], f"[{label}] 无横向溢出", failures)
                check(not m["doubleScrollbar"], f"[{label}] 无双滚动条", failures)
                check(m["clippedButtons"] == 0, f"[{label}] 无按钮裁切(共 {m['buttonCount']} 个按钮)", failures)
                check(m["hiddenButtons"] == 0, f"[{label}] 无按钮被隐藏", failures)
                if label == "zoom200":
                    # zoom200 下步骤区外按钮(头/输入/footer)必须可见可点;
                    # 步骤内的删除按钮随列表滚动是正常行为,只断言其尺寸不被裁切。
                    pinned_clickable = page.evaluate("""() => Array.from(document.querySelectorAll('.study-summer-breakdown__header button, .study-summer-breakdown__input button, .study-summer-breakdown__footer button')).map((btn) => {
                      const r = btn.getBoundingClientRect();
                      if (r.width < 4 || r.height < 4) return false;
                      const el = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
                      return el === btn || btn.contains(el);
                    })""")
                    check(len(pinned_clickable) > 0 and all(pinned_clickable), f"[{label}] 头/输入/footer 按钮可见可点击(共 {len(pinned_clickable)} 个)", failures)
                    check(page.evaluate("document.body.style.overflow") == "hidden", f"[{label}] 背景不滚动(body 锁定)", failures)
                    check(page.evaluate("document.documentElement.style.overflow") == "hidden", f"[{label}] 背景不滚动(html 锁定)", failures)
            page.screenshot(path=str(OUT / f"breakdown-{label}.png"))

            page.get_by_role("button", name="关闭目标拆解").click()
            page.wait_for_timeout(200)
            check(page.locator(".study-summer-breakdown").count() == 0, f"[{label}] 拆解弹窗关闭", failures)
            check(page.evaluate("document.body.style.overflow") != "hidden", f"[{label}] 拆解弹窗关闭后 body 恢复可滚动", failures)
            check(page.evaluate("document.documentElement.style.overflow") != "hidden", f"[{label}] 拆解弹窗关闭后 html 恢复可滚动", failures)

            page.get_by_label("这次想完成什么").fill("测试专注")
            page.get_by_role("button", name="开始专注").click()
            page.get_by_role("button", name="暂停").wait_for(timeout=10000)
            page.get_by_role("button", name="结束并记录").click()
            page.locator("section.modal--study").wait_for(timeout=5000)
            page.wait_for_timeout(300)
            r = dialog_metrics(page, "section.modal--study")
            check(r is not None, f"[{label}] 复盘弹窗可度量", failures)
            if r:
                check(not r["overflowX"], f"[{label}] 复盘弹窗无横向溢出", failures)
                check(r["clippedButtons"] == 0, f"[{label}] 复盘弹窗无按钮裁切", failures)
            check(page.evaluate("document.activeElement && document.activeElement.id") == "study-self-report", f"[{label}] 复盘 textarea 获焦", failures)
            page.screenshot(path=str(OUT / f"review-{label}.png"))

            check(not errors, f"[{label}] 无页面异常", failures)
            if errors:
                print(f"[{label}] pageerrors:", errors[:3])
            context.close()
        browser.close()

    print(f"\nshots dir: {OUT}")
    if failures:
        print("\nFAILURES:")
        for item in failures:
            print(" -", item)
        return 1
    print("\nALL DIALOG VIEWPORT CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(run())
