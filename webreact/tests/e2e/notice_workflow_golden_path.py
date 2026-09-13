"""路径 2: 校园通知事务黄金路径(Playwright)。

流程: 登录 → 粘贴通知(UI) → 创建流程(UI) → 显示动作清单与风险(UI) →
同意并执行动作(UI) → 页面显示 Action 状态。

运行前提: 后端(fake provider)与前端 dev 已启动,环境变量 WEB_BASE_URL/API_BASE_URL/DEMO_USERNAME/DEMO_PASSWORD。
不使用固定 sleep,用 Playwright 等待断言。截图不落盘。
"""
from __future__ import annotations

import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5184")
API_BASE = os.environ.get("API_BASE_URL", "http://127.0.0.1:8765/api/v1")
DEMO_USERNAME = os.environ.get("DEMO_USERNAME", "student_demo")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "Demo123456")

# AUTO_SAFE 通知:产生 create_task / generate_checklist / add_reminder 动作
NOTICE_CONTENT = "请于2026年10月15日前提交奖学金申请表至教务处,逾期不予受理"
NOTICE_SOURCE = "E2E教务处公告"


def _check(condition, message, failures):
    print(("PASS " if condition else "FAIL ") + message)
    if not condition:
        failures.append(message)


def _api_get(page, path):
    return page.evaluate(
        """async ([apiBase, path]) => {
          const token = localStorage.getItem('campus_access_token');
          const resp = await fetch(apiBase + path, { headers: { Authorization: 'Bearer ' + token } });
          return { status: resp.status, body: await resp.json() };
        }""",
        [API_BASE, path],
    )


def _login(page, failures):
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.get_by_placeholder("请输入学号或用户名").fill(DEMO_USERNAME)
    page.get_by_placeholder("请输入密码").fill(DEMO_PASSWORD)
    page.get_by_role("button", name="登录", exact=True).click()
    page.wait_for_url("**/home", timeout=15000)
    token = page.evaluate("() => localStorage.getItem('campus_access_token')")
    _check(bool(token), "登录后写入 access_token", failures)


def run():
    failures = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        try:
            _login(page, failures)

            # 导航到通知事务工作台
            page.goto(f"{BASE}/agent/notice-workflow", wait_until="networkidle")
            page.locator(".notice-workflow-workspace").wait_for(timeout=15000)

            # 粘贴通知内容并创建流程
            page.get_by_placeholder("粘贴校园通知、教务公告或 Chaoxing 消息原文").fill(NOTICE_CONTENT)
            page.get_by_placeholder("例如：教务处公告 / 班群通知").fill(NOTICE_SOURCE)
            page.get_by_role("button", name="创建流程").click()

            # 等待动作清单出现
            action_list = page.locator(".action-list")
            action_list.wait_for(timeout=20000)
            action_count = action_list.locator("li").count()
            _check(action_count >= 1, f"动作清单显示动作(count={action_count})", failures)

            # 验证风险标签存在
            risk_labels = page.locator(".action-risk").count()
            _check(risk_labels >= 1, f"显示风险等级标签(count={risk_labels})", failures)

            # 同意第一个可操作动作(AUTO_SAFE 的"同意"按钮)
            approve_btn = page.locator(".action-list button:has-text('同意')").first
            approve_btn.wait_for(timeout=10000)
            approve_btn.click()

            # 等待动作状态更新(refreshWorkflow 会调 getNoticeWorkflow 刷新)
            try:
                page.wait_for_function(
                    """() => {
                      const statuses = Array.from(document.querySelectorAll('.action-status')).map(el => el.textContent || '');
                      return statuses.some(s => s.includes('已完成'));
                    }""",
                    timeout=15000,
                )
                action_done = True
            except Exception:
                action_done = False
            _check(action_done, "同意后动作状态更新为已完成", failures)

            # 验证流程详情仍显示
            view_meta = page.locator(".workflow-meta")
            view_meta.wait_for(timeout=5000)
            status_text = view_meta.inner_text()
            _check("流程状态" in status_text, "页面显示流程状态", failures)

            # 验证风险标签与动作清单仍可见
            risk_labels = page.locator(".action-risk").count()
            _check(risk_labels >= 1, f"页面显示风险标签(count={risk_labels})", failures)

            _check(not errors, "无页面异常", failures)
            if errors:
                print("pageerrors:", errors[:3])
        except Exception as exc:
            _check(False, f"未预期异常: {type(exc).__name__}: {exc}", failures)
        finally:
            browser.close()

    if failures:
        print("\nFAILURES:")
        for item in failures:
            print(" -", item)
        return 1
    print("\nALL NOTICE WORKFLOW GOLDEN PATH CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(run())