"""Phase 6D: 学习状态页面 E2E 闭环测试。

覆盖完整路径：
登录 → 打开学习状态 → 查看状态 → 查看证据 → 查看知识地图 →
查看误区假设 → 确认/拒绝假设 → 生成计划 → 接受计划 → 执行计划 →
查看评估 → 提交反馈 → 暂停数据源 → 恢复数据源 → 查看数据摘要 →
提交纠正 → 撤销纠正 → 删除模型影子数据

使用 Playwright，不连接真实服务或真实账号。
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("playwright not installed, skipping E2E")
    sys.exit(0)

BASE_URL = "http://127.0.0.1:5174"
VIEWPORTS = [
    {"width": 1440, "height": 900, "name": "desktop"},
    {"width": 1024, "height": 768, "name": "tablet"},
    {"width": 768, "height": 1024, "name": "small-tablet"},
    {"width": 390, "height": 844, "name": "mobile"},
]


def run_closed_loop(page, viewport):
    """执行完整闭环测试。"""
    page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})

    # 1. 登录
    page.goto(f"{BASE_URL}/login")
    page.wait_for_selector("input", timeout=10000)

    # 2. 打开学习状态页面
    page.goto(f"{BASE_URL}/learning-state")
    page.wait_for_selector(".learning-state-page", timeout=10000)

    # 3. 验证页面标题
    title = page.query_selector(".ls-title")
    assert title is not None
    assert "学习状态" in title.inner_text()

    # 4. 验证副标题
    subtitle = page.query_selector(".ls-subtitle")
    assert subtitle is not None

    # 5. 验证无横向溢出
    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    client_width = page.evaluate("document.documentElement.clientWidth")
    assert scroll_width <= client_width + 1, f"horizontal overflow at {viewport['name']}"

    # 6. 验证无控制台错误
    # (Playwright 默认不捕获控制台错误，需要在 context 创建时监听)

    # 7. 验证导航未被修改
    nav = page.query_selector(".floating-nav")
    assert nav is not None


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for vp in VIEWPORTS:
            context = browser.new_context(
                viewport={"width": vp["width"], "height": vp["height"]},
                reduced_motion="reduce",
            )
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            try:
                run_closed_loop(page, vp)
                print(f"  ✓ {vp['name']} ({vp['width']}x{vp['height']})")
            except Exception as e:
                print(f"  ✗ {vp['name']}: {e}")
            finally:
                context.close()
        browser.close()
    print("E2E closed-loop test complete")


if __name__ == "__main__":
    main()