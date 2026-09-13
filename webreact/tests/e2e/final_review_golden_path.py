"""路径 1: 期末复习黄金路径(Playwright)。

流程: 登录 → 创建考试(API) → 创建活动(UI) → 生成计划提案(UI) → 审批同意(UI) →
查看今日日程(UI) → 提交每日签到(API) → 页面显示最新状态。

运行前提: 后端(fake provider)与前端 dev 已启动,环境变量 WEB_BASE_URL/API_BASE_URL/DEMO_USERNAME/DEMO_PASSWORD。
不使用固定 sleep,用 Playwright 等待断言。截图不落盘。
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

BASE = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5184")
API_BASE = os.environ.get("API_BASE_URL", "http://127.0.0.1:8765/api/v1")
DEMO_USERNAME = os.environ.get("DEMO_USERNAME", "student_demo")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "Demo123456")

EXAM_COURSE = "E2E期末复习数学"
EXAM_DATE = "2026-12-30"


def _check(condition, message, failures):
    print(("PASS " if condition else "FAIL ") + message)
    if not condition:
        failures.append(message)


def _api_get(page, path):
    """用页面 localStorage token 调 GET API。"""
    return page.evaluate(
        """async ([apiBase, path]) => {
          const token = localStorage.getItem('campus_access_token');
          const resp = await fetch(apiBase + path, { headers: { Authorization: 'Bearer ' + token } });
          return { status: resp.status, body: await resp.json() };
        }""",
        [API_BASE, path],
    )


def _api_post(page, path, body):
    """用页面 localStorage token 调 POST API。"""
    return page.evaluate(
        """async ([apiBase, path, body]) => {
          const token = localStorage.getItem('campus_access_token');
          const resp = await fetch(apiBase + path, {
            method: 'POST',
            headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
          });
          const text = await resp.text();
          let parsed = null;
          try { parsed = JSON.parse(text); } catch {}
          return { status: resp.status, body: parsed, text };
        }""",
        [API_BASE, path, body],
    )


def _login(page, failures):
    """通过 UI 登录。"""
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.get_by_placeholder("请输入学号或用户名").fill(DEMO_USERNAME)
    page.get_by_placeholder("请输入密码").fill(DEMO_PASSWORD)
    page.get_by_role("button", name="登录", exact=True).click()
    page.wait_for_url("**/home", timeout=15000)
    token = page.evaluate("() => localStorage.getItem('campus_access_token')")
    _check(bool(token), "登录后写入 access_token", failures)


def _create_exam(page, failures):
    """通过 API 创建考试,返回 exam_id。"""
    result = _api_post(page, "/student/exams", {"course_name": EXAM_COURSE, "exam_date": EXAM_DATE})
    _check(result["status"] == 201, f"创建考试成功(status={result['status']})", failures)
    return result["body"]["id"]


def run():
    failures = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        try:
            _login(page, failures)
            exam_id = _create_exam(page, failures)

            # 导航到期末复习工作台
            page.goto(f"{BASE}/agent/final-review", wait_until="networkidle")
            page.locator(".final-review-workspace").wait_for(timeout=15000)

            # 选择考试并创建活动
            exam_checkbox = page.get_by_role("checkbox", name=f"选择考试 {EXAM_COURSE}")
            exam_checkbox.wait_for(timeout=10000)
            exam_checkbox.check()
            page.get_by_role("button", name="创建活动", exact=True).click()

            # 等待计划视图出现(表示 campaign 已创建)
            page.get_by_role("button", name="生成计划提案").wait_for(timeout=15000)

            # 生成计划提案
            page.get_by_role("button", name="生成计划提案").click()
            # 等待审批面板出现
            approval_btn = page.get_by_role("button", name="同意")
            approval_btn.wait_for(timeout=20000)

            # 同意审批(会自动激活计划)
            approval_btn.click()

            # 通过 API 只定位本次 campaign；签到必须经由 Web UI 完成。
            campaigns = _api_get(page, "/final-review/campaigns?page_size=10")
            _check(campaigns["status"] == 200, "获取 campaign 列表成功", failures)
            campaign_id = None
            for c in campaigns["body"]:
                if exam_id in (c.get("exam_ids") or []):
                    campaign_id = c["campaign_id"]
                    break
            _check(campaign_id is not None, "找到刚创建的 campaign", failures)

            if campaign_id:
                checkin_form = page.locator(".daily-checkin-form")
                checkin_form.wait_for(timeout=15000)
                completed_boxes = checkin_form.get_by_role("checkbox", name="标记已完成")
                for index in range(completed_boxes.count()):
                    completed_boxes.nth(index).check()
                checkin_form.get_by_role("button", name="提交今日签到").click()
                page.get_by_text("今日签到已记录", exact=True).wait_for(timeout=15000)
                _check(True, "通过 Web UI 提交每日签到", failures)

            # 刷新页面验证最新状态
            page.reload(wait_until="networkidle")
            page.locator(".final-review-workspace").wait_for(timeout=15000)
            # 验证计划版本区域存在(表示 campaign 已激活)
            version_list = page.locator(".version-list")
            version_list.wait_for(timeout=10000)
            version_count = version_list.locator("li").count()
            _check(version_count >= 1, f"刷新后显示计划版本(count={version_count})", failures)

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
    print("\nALL FINAL REVIEW GOLDEN PATH CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(run())
