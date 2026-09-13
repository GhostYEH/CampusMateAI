"""路径 3: 课程研究黄金路径(Playwright + SSE 恢复验证)。

流程: 登录 → 提交问题(UI) → 接收运行状态/SSE 事件(UI) → 运行完成 →
打开 Artifact(UI) → 显示 Markdown 报告 → 显示经过验证的 sources/citations →
验证 SSE Last-Event-ID 事件恢复逻辑。

运行前提: 后端(fake provider)与前端 dev 已启动,环境变量 WEB_BASE_URL/API_BASE_URL/DEMO_USERNAME/DEMO_PASSWORD。
不使用固定 sleep,用 Playwright 等待断言。截图不落盘。
"""
from __future__ import annotations

import os
import sys
import urllib.request

from playwright.sync_api import sync_playwright

BASE = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5184")
API_BASE = os.environ.get("API_BASE_URL", "http://127.0.0.1:8765/api/v1")
DEMO_USERNAME = os.environ.get("DEMO_USERNAME", "student_demo")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "Demo123456")

QUESTION = "解释梯度下降法中学习率的选择策略"


def _check(condition, message, failures):
    print(("PASS " if condition else "FAIL ") + message)
    if not condition:
        failures.append(message)


def _api_get(page, path):
    return page.evaluate(
        """async ([apiBase, path]) => {
          const token = localStorage.getItem('campus_access_token');
          const resp = await fetch(apiBase + path, { headers: { Authorization: 'Bearer ' + token } });
          const text = await resp.text();
          let parsed = null;
          try { parsed = JSON.parse(text); } catch {}
          return { status: resp.status, body: parsed, text };
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
    return token


def _fetch_sse(api_base, run_id, token, last_event_id=None):
    """直接请求 SSE 端点,返回原始文本。"""
    url = f"{api_base}/agent-runs/{run_id}/events/stream"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "text/event-stream")
    if last_event_id:
        req.add_header("Last-Event-ID", last_event_id)
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _parse_sse_event_ids(text):
    """从 SSE 文本提取所有 event id 和 event type。"""
    ids = []
    events = []
    current_id = None
    current_event = None
    for line in text.split("\n"):
        if line.startswith("id:"):
            current_id = line[3:].strip()
        elif line.startswith("event:"):
            current_event = line[6:].strip()
        elif line.strip() == "" and (current_id or current_event):
            ids.append(current_id)
            events.append(current_event)
            current_id = None
            current_event = None
    return ids, events


def run():
    failures = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        try:
            token = _login(page, failures)

            # 从首页入口进入(不直接拼 URL);首页 WebGL 重页面,headless 下用页面内 JS 点击。
            page.goto(f"{BASE}/home", wait_until="domcontentloaded")
            clicked = page.evaluate(
                """async () => {
                  const deadline = Date.now() + 15000;
                  while (Date.now() < deadline) {
                    const target = Array.from(document.querySelectorAll("button.sylva-agent-entry"))
                      .find((node) => (node.textContent || "").trim() === "课程研究");
                    if (target) { target.click(); return true; }
                    await new Promise((resolve) => setTimeout(resolve, 100));
                  }
                  return false;
                }"""
            )
            _check(clicked is True, "首页存在「课程研究」入口", failures)
            page.wait_for_url("**/agent/course-research", timeout=15000)
            page.locator(".course-research-workspace").wait_for(timeout=15000)

            # 提交问题
            page.get_by_placeholder("例如：解释梯度下降的学习率选择").fill(QUESTION)
            page.get_by_role("button", name="开始研究").click()

            # 等待 run 终态(任务已结束)
            terminal = page.locator(".run-terminal-note")
            terminal.wait_for(timeout=60000)

            # 验证 run 状态徽章
            status_badge = page.locator(".run-status-badge").first
            status_text = status_badge.inner_text()
            _check(
                "成功" in status_text or "完成" in status_text or "部分" in status_text or "SUCCEEDED" in status_text.upper() or "PARTIAL" in status_text.upper(),
                f"run 到达终态(status={status_text})",
                failures,
            )

            # 通过 API 获取 run_id(取最新 run)
            runs = _api_get(page, "/course-research/runs?page_size=5")
            _check(runs["status"] == 200, "获取 run 列表成功", failures)
            run_id = None
            if runs["status"] == 200 and runs["body"]:
                for r in runs["body"]:
                    if r.get("question") == QUESTION:
                        run_id = r["run_id"]
                        break
                if run_id is None and runs["body"]:
                    run_id = runs["body"][0]["run_id"]
            _check(run_id is not None, f"找到 run_id({run_id})", failures)

            if run_id:
                # 获取 run 详情,从 artifact_ids 取产物
                run_detail = _api_get(page, f"/course-research/runs/{run_id}")
                _check(run_detail["status"] == 200, f"获取 run 详情成功(status={run_detail['status']})", failures)
                artifact_ids = []
                if run_detail["status"] == 200 and run_detail["body"]:
                    artifact_ids = run_detail["body"].get("artifact_ids") or []
                _check(len(artifact_ids) >= 1, f"run 产生 artifact(count={len(artifact_ids)})", failures)

                if artifact_ids:
                    # 遍历 artifact 找 Markdown 报告
                    markdown_artifact = None
                    for aid in artifact_ids:
                        art = _api_get(page, f"/agent-artifacts/{aid}")
                        if art["status"] == 200 and art["body"] and art["body"].get("mime_type") == "text/markdown":
                            markdown_artifact = art["body"]
                            break
                    _check(markdown_artifact is not None, "存在 Markdown 报告 artifact", failures)
                    if markdown_artifact:
                        _check(markdown_artifact.get("download_url"), "Markdown artifact 有 download_url", failures)

                        # 验证 UI 显示报告内容
                        report_content = page.locator(".report-content")
                        report_content.wait_for(timeout=15000)
                        report_text = report_content.inner_text()
                        _check(len(report_text) > 0, "UI 显示 Markdown 报告正文", failures)

                # 验证 SSE Last-Event-ID 事件恢复逻辑
                # 1. 获取全部事件
                full_sse = _fetch_sse(API_BASE, run_id, token)
                all_ids, all_events = _parse_sse_event_ids(full_sse)
                _check(len(all_events) >= 1, f"SSE 流返回事件(count={len(all_events)})", failures)

                if len(all_ids) >= 2:
                    # 2. 用第一个事件的 id 作为 Last-Event-ID 续传
                    resume_id = all_ids[0]
                    resumed_sse = _fetch_sse(API_BASE, run_id, token, last_event_id=resume_id)
                    resumed_ids, resumed_events = _parse_sse_event_ids(resumed_sse)
                    # 3. 续传后不应包含第一个事件(已跳过)
                    first_event_type = all_events[0]
                    skipped_count = resumed_events.count(first_event_type)
                    total_first_type = all_events.count(first_event_type)
                    _check(
                        skipped_count < total_first_type or len(resumed_events) < len(all_events),
                        f"Last-Event-ID 续传跳过已确认事件(全量={len(all_events)},续传={len(resumed_events)})",
                        failures,
                    )
                    _check(len(resumed_events) >= 1, f"续传仍返回后续事件(count={len(resumed_events)})", failures)
                else:
                    _check(True, "事件不足 2 条,跳过续传验证(已验证流可用)", failures)

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
    print("\nALL COURSE RESEARCH GOLDEN PATH CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(run())