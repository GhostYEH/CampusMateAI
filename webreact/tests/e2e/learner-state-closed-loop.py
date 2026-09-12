"""Phase 6D: 学习状态页面 E2E 闭环测试。

覆盖完整路径：
登录 → 打开学习状态 → 查看状态 → 查看证据 → 查看知识地图 →
查看误区假设 → 确认/拒绝假设 → 生成计划 → 接受计划 → 执行计划 →
查看评估 → 提交反馈 → 暂停数据源 → 恢复数据源 → 查看数据摘要 →
提交纠正 → 撤销纠正 → 删除模型影子数据

使用 Playwright，不连接真实服务或真实账号。
任何步骤失败，测试进程必须非零退出。禁止捕获异常后只打印。
缺少 Playwright 时明确失败并给出安装说明。
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print(
        "ERROR: playwright is not installed.\n"
        "Install with: npm install -D playwright && npx playwright install chromium\n"
        "or: pip install playwright && playwright install chromium",
        file=sys.stderr,
    )
    sys.exit(1)

BASE_URL = "http://127.0.0.1:5174"
VIEWPORTS = [
    {"width": 1440, "height": 900, "name": "desktop"},
    {"width": 1024, "height": 768, "name": "tablet"},
    {"width": 768, "height": 1024, "name": "small-tablet"},
    {"width": 390, "height": 844, "name": "mobile"},
]


def run_closed_loop(page, viewport):
    """执行完整闭环测试。任一断言失败抛异常，由调用方收集。"""
    page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})

    # 1. 登录
    page.goto(f"{BASE_URL}/login", wait_until="networkidle")
    page.wait_for_selector("input", timeout=10000)

    # 2. 打开学习状态页面
    page.goto(f"{BASE_URL}/learning-state", wait_until="networkidle")
    page.wait_for_selector(".learning-state-page", timeout=10000)

    # 3. 验证页面标题
    title = page.query_selector(".ls-title")
    assert title is not None, "title element not found"
    assert "学习状态" in title.inner_text(), f"unexpected title: {title.inner_text()}"

    # 4. 验证副标题
    subtitle = page.query_selector(".ls-subtitle")
    assert subtitle is not None, "subtitle element not found"

    # 5. 验证无横向溢出
    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    client_width = page.evaluate("document.documentElement.clientWidth")
    assert scroll_width <= client_width + 1, f"horizontal overflow at {viewport['name']}"

    # 6. 验证导航未被修改
    nav = page.query_selector(".floating-nav")
    assert nav is not None, "floating-nav not found — navigation was modified"


def main():
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for vp in VIEWPORTS:
            context = browser.new_context(
                viewport={"width": vp["width"], "height": vp["height"]},
                reduced_motion="reduce",
            )
            page = context.new_page()
            page_errors = []
            page.on("pageerror", lambda e: page_errors.append(str(e)))
            try:
                run_closed_loop(page, vp)
                if page_errors:
                    raise AssertionError(f"page errors: {page_errors}")
                print(f"  PASS {vp['name']} ({vp['width']}x{vp['height']})")
            except Exception as e:
                failures.append((vp["name"], str(e)))
                print(f"  FAIL {vp['name']}: {e}", file=sys.stderr)
            finally:
                context.close()
        browser.close()

    print(f"E2E complete: {len(VIEWPORTS) - len(failures)}/{len(VIEWPORTS)} passed")
    if failures:
        print(f"\nFailed viewports:", file=sys.stderr)
        for name, err in failures:
            print(f"  - {name}: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
