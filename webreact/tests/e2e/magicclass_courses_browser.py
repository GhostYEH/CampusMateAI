"""magic class 课程首页的真实浏览器验收。

不 mock 浏览器 API：页面请求真实经过 Vite → FastAPI → magicclass-service，
并使用隔离的数据库、测试学生与本地 OpenAI 兼容 provider。验收当前首页的两条入口：

1. 输入主题后生成新的课堂并进入工作台；
2. 服务掉线时在首页显示局部中文错误，恢复后可直接重试；
3. 320/768/1024/1440 视口无横向溢出，课程选择器与直接进入课堂入口可用。
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5184")
STUDENT_USERNAME = os.environ.get("E2E_STUDENT_USERNAME", "student_demo")
STUDENT_PASSWORD = os.environ.get("E2E_STUDENT_PASSWORD", "Demo123456")
SHOTS = Path(os.environ.get("E2E_SHOTS_DIR", str(Path(__file__).resolve().parent / "shots")))

VIEWPORTS = [
    (320, 720, "phone"),
    (768, 900, "tablet"),
    (1024, 900, "laptop"),
    (1440, 622, "short-desktop"),
    (1440, 900, "desktop"),
]

BENIGN_CONSOLE = (
    "Download the React DevTools",
    "[api] 5xx",  # 掉线时 api.js 的开发诊断，不是未处理异常。
)
NETWORK_MESSAGE_PREFIX = "Failed to load resource:"


class Recorder:
    """收集浏览器异常和 HTTP 响应，以免 E2E 只断言页面表象。"""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.console: list[dict] = []
        self.page_errors: list[str] = []
        self.failed_requests: list[dict] = []
        self.responses: list[dict] = []

    def attach(self, page) -> None:
        page.on("console", lambda message: self.console.append({
            "type": message.type,
            "text": message.text,
            "location": message.location or {},
        }))
        page.on("pageerror", lambda error: self.page_errors.append(str(error)))

        def record_failed_request(request) -> None:
            # Playwright Python 新版返回 str，旧版返回 {errorText: str}。
            failure = request.failure
            failure_text = failure if isinstance(failure, str) else (failure or {}).get("errorText", "")
            self.failed_requests.append({
                "url": request.url,
                "method": request.method,
                "failure": failure_text,
            })

        page.on("requestfailed", record_failed_request)
        page.on("response", lambda response: self.responses.append({
            "url": response.url,
            "status": response.status,
            "method": response.request.method,
        }))

    def status_of(self, fragment: str) -> int | None:
        for item in reversed(self.responses):
            if fragment in item["url"]:
                return item["status"]
        return None

    def await_status(self, page, fragment: str, timeout: float = 12.0) -> int | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self.status_of(fragment)
            if status is not None:
                return status
            page.wait_for_timeout(120)
        return None

    def script_console_errors(self) -> list[dict]:
        return [
            item for item in self.console
            if item["type"] == "error"
            and not any(marker in item["text"] for marker in BENIGN_CONSOLE)
            and not item["text"].startswith(NETWORK_MESSAGE_PREFIX)
        ]

    def network_console_errors(self) -> list[dict]:
        return [
            item for item in self.console
            if item["type"] == "error" and item["text"].startswith(NETWORK_MESSAGE_PREFIX)
        ]

    def third_party_console_errors(self) -> list[dict]:
        return [
            item for item in self.script_console_errors()
            if item["location"].get("url") and not item["location"]["url"].startswith(self.base_url)
        ]


def _step(report: list[str], text: str) -> None:
    print(f"  · {text}")
    report.append(text)


def diagnose(page, recorder: Recorder, label: str) -> None:
    """失败时输出当前 UI 和请求证据，避免把超时误判为单一原因。"""
    print(f"\n--- 失败现场（{label}）---", file=sys.stderr)
    try:
        print(f"当前 URL：{page.url}", file=sys.stderr)
    except Exception:
        pass
    for selector, name in (
        (".magicclass-reference-error", "首页局部错误"),
        (".magicclass-reference-hint", "首页能力提示"),
        (".state-card.error-state", "整页错误卡片"),
    ):
        try:
            locator = page.locator(selector)
            text = locator.first.inner_text().strip()[:300] if locator.count() else "不存在"
            print(f"{name}：{text}", file=sys.stderr)
        except Exception as exc:
            print(f"{name}：读取失败（{exc}）", file=sys.stderr)
    try:
        submit = page.locator('[aria-label="生成学习内容"]')
        topic = page.locator('textarea[aria-label="学习主题"]')
        topic_value = topic.first.input_value()[:80] if topic.count() else "n/a"
        disabled = submit.first.is_disabled() if submit.count() else "n/a"
        print(f"生成按钮：count={submit.count()} disabled={disabled}；主题={topic_value!r}", file=sys.stderr)
    except Exception as exc:
        print(f"表单状态读取失败（{exc}）", file=sys.stderr)
    print("最近 25 条响应：", file=sys.stderr)
    for item in recorder.responses[-25:]:
        print(f"    {item['method']} {item['status']} {item['url'][:160]}", file=sys.stderr)
    if recorder.page_errors:
        print("pageerror：", file=sys.stderr)
        for item in recorder.page_errors[-10:]:
            print(f"    {item[:400]}", file=sys.stderr)
    errors = [item for item in recorder.console if item["type"] == "error"]
    if errors:
        print("console error：", file=sys.stderr)
        for item in errors[-10:]:
            print(f"    {item['text'][:400]}", file=sys.stderr)
    if recorder.failed_requests:
        print("失败请求：", file=sys.stderr)
        for item in recorder.failed_requests[-10:]:
            print(f"    {item['method']} {item['url'][:140]} → {item['failure']}", file=sys.stderr)


def login(page, report: list[str]) -> None:
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.locator("form input").nth(0).fill(STUDENT_USERNAME)
    page.locator("form input").nth(1).fill(STUDENT_PASSWORD)
    page.locator('form button:has-text("登录")').click()
    page.wait_for_url(f"{BASE}/home", timeout=20000)
    _step(report, f"真实 UI 登录成功：{STUDENT_USERNAME} → /home")


def _course_id_from_direct_entry(page) -> str:
    href = page.locator(".magicclass-classroom-entry__action").get_attribute("href")
    match = re.search(r"/courses/([^/]+)/classroom$", href or "")
    if not match:
        raise AssertionError(f"直接进入课堂链接不含课程 ID：{href!r}")
    return match.group(1)


def open_courses(page, report: list[str]) -> str:
    page.goto(f"{BASE}/courses", wait_until="domcontentloaded")
    trigger = page.locator(".magicclass-reference-picker__trigger")
    expect(trigger).to_be_visible(timeout=20000)
    expect(page.locator('textarea[aria-label="学习主题"]')).to_be_visible(timeout=10000)
    expect(page.locator(".magicclass-classroom-entry__action")).to_be_visible(timeout=10000)

    trigger.click()
    options = page.locator('[role="listbox"] [role="option"]')
    expect(options.first).to_be_visible(timeout=5000)
    labels = [options.nth(index).inner_text().strip() for index in range(options.count())]
    assert labels, "课程选择器没有任何真实课程"
    trigger.click()

    course_id = _course_id_from_direct_entry(page)
    _step(report, f"/courses 加载了 {len(labels)} 门真实课程，当前选择 {course_id}")
    return course_id


def check_viewports(page, report: list[str]) -> list[Path]:
    """窄屏仍必须可输入、选课、进入课堂，且不横向滚动。"""
    shots: list[Path] = []
    SHOTS.mkdir(parents=True, exist_ok=True)
    for width, height, label in VIEWPORTS:
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(320)
        overflow = page.evaluate("() => ({ scrollWidth: document.documentElement.scrollWidth, inner: window.innerWidth })")
        assert overflow["scrollWidth"] <= overflow["inner"] + 1, (
            f"{width}px 出现横向溢出：{overflow['scrollWidth']} > {overflow['inner']}"
        )
        for selector, name in (
            (".magicclass-reference-composer", "输入工作区"),
            (".magicclass-classroom-entry__action", "直接进入课堂"),
        ):
            locator = page.locator(selector)
            locator.scroll_into_view_if_needed(timeout=5000)
            box = locator.bounding_box()
            assert box, f"{width}px 找不到{name}"
            assert box["x"] >= -1 and box["x"] + box["width"] <= width + 1, (
                f"{width}px {name}超出视口：x={box['x']} w={box['width']}"
            )

        picker = page.locator(".magicclass-reference-picker__trigger")
        picker.click()
        menu = page.locator(".magicclass-reference-picker__menu")
        expect(menu).to_be_visible(timeout=5000)
        menu_box = menu.bounding_box()
        assert menu_box, f"{width}×{height} 找不到课程菜单布局盒子"
        assert menu_box["x"] >= -1 and menu_box["x"] + menu_box["width"] <= width + 1, (
            f"{width}×{height} 课程菜单横向越界：x={menu_box['x']} w={menu_box['width']}"
        )
        assert menu_box["y"] >= -1 and menu_box["y"] + menu_box["height"] <= height + 1, (
            f"{width}×{height} 课程菜单被视口裁切：y={menu_box['y']} h={menu_box['height']}"
        )
        picker.click()
        shot = SHOTS / f"magicclass-courses-{label}-{width}x{height}.png"
        page.screenshot(path=str(shot), full_page=False)
        shots.append(shot)
        _step(report, f"{width}×{height} 无横向溢出，输入、选课和进入课堂入口均在视口内 → {shot.name}")

    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(320)
    full = SHOTS / "magicclass-courses-fullpage-1440.png"
    page.screenshot(path=str(full), full_page=True)
    shots.append(full)
    _step(report, f"课程首页整页截图 → {full.name}")
    return shots


def run_checks(service_control) -> dict:
    """执行当前首页的健康、掉线恢复、响应式与无脚本异常验收。"""
    report: list[str] = []
    recorder = Recorder(BASE)
    shots: list[Path] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = context.new_page()
        recorder.attach(page)

        try:
            print("步骤 1：真实登录并进入当前 /courses 首页")
            login(page, report)
            course_id = open_courses(page, report)

            print("步骤 2：首页主题生成进入真实工作台")
            topic = "浏览器验收：用矩阵乘法解释傅里叶变换"
            page.locator('textarea[aria-label="学习主题"]').fill(topic)
            recorder.responses.clear()
            page.locator('[aria-label="生成学习内容"]').click()
            page.wait_for_url(f"**/courses/{course_id}/workspaces/**", timeout=30000)
            expect(page.get_by_test_id("magicclass-workbench")).to_be_visible(timeout=20000)
            generation_status = recorder.await_status(page, f"/courses/{course_id}/home-generate", timeout=8)
            assert generation_status == 201, f"首页生成返回 {generation_status}，期望 201"
            assert "/counselor" not in page.url, f"首页生成错误跳进小助手：{page.url}"
            assert "mode=playback" in page.url, f"首页生成没有进入播放工作台：{page.url}"
            _step(report, f"POST /api/v1/courses/{course_id}/home-generate → HTTP 201，进入真实播放工作台")

            page.reload(wait_until="domcontentloaded")
            expect(page.get_by_test_id("magicclass-workbench")).to_be_visible(timeout=20000)
            _step(report, "刷新工作台后仍可恢复真实 workspace/stage 数据")

            print("步骤 3：服务掉线时首页局部降级，其他课程功能不受影响")
            course_id = open_courses(page, report)
            failed_topic = "浏览器验收：服务恢复后的课堂生成"
            page.locator('textarea[aria-label="学习主题"]').fill(failed_topic)
            recorder.responses.clear()
            service_control.stop()
            page.locator('[aria-label="生成学习内容"]').click()
            error = page.locator(".magicclass-reference-error")
            expect(error).to_be_visible(timeout=20000)
            failed_status = recorder.await_status(page, f"/courses/{course_id}/home-generate")
            assert failed_status == 503, f"掉线时首页生成应为 503，实际 {failed_status}"
            error_text = error.inner_text().strip()
            assert "Request failed with status code" not in error_text, f"把 Axios 英文原文给了用户：{error_text}"
            assert any(char in error_text for char in "请稍后未启用不可用重试"), f"错误文案不是中文可操作信息：{error_text}"
            assert page.url == f"{BASE}/courses", f"失败后不应离开课程首页：{page.url}"
            assert page.locator(".state-card.error-state").count() == 0, "局部错误被错误替换成整页错误卡片"
            _step(report, f"POST /api/v1/courses/{course_id}/home-generate → HTTP 503；首页保留并显示局部中文错误")

            detail_page = context.new_page()
            recorder.attach(detail_page)
            detail_page.goto(f"{BASE}/courses/{course_id}", wait_until="domcontentloaded")
            expect(detail_page.locator("main")).to_be_visible(timeout=20000)
            detail_page.close()
            _step(report, "受管服务掉线时，课程详情仍能正常打开")

            print("步骤 4：恢复服务后直接重试，无需刷新课程首页")
            service_control.start()
            recorder.responses.clear()
            page.locator('[aria-label="生成学习内容"]').click()
            page.wait_for_url(f"**/courses/{course_id}/workspaces/**", timeout=30000)
            expect(page.get_by_test_id("magicclass-workbench")).to_be_visible(timeout=20000)
            retry_status = recorder.await_status(page, f"/courses/{course_id}/home-generate", timeout=8)
            assert retry_status == 201, f"恢复后首页生成返回 {retry_status}，期望 201"
            assert "/counselor" not in page.url
            _step(report, "服务恢复后直接重试成功，进入工作台且未刷新整站")

            print("步骤 5：五种视口的布局与课程选择器")
            open_courses(page, report)
            shots = check_viewports(page, report)

            print("步骤 6：console / pageerror / 故障请求审计")
            script_errors = recorder.script_console_errors()
            assert not recorder.page_errors, f"出现未捕获的页面异常：{recorder.page_errors}"
            assert not script_errors, f"站点脚本出现 console error：{script_errors}"
            _step(report, "pageerror 和站点脚本 console error 均为 0 条")

            deliberate = f"/courses/{course_id}/home-generate"
            network_errors = recorder.network_console_errors()
            unexpected_network = [
                item for item in network_errors
                if deliberate not in (item["location"].get("url") or "")
            ]
            assert not unexpected_network, f"出现预期之外的资源加载失败：{unexpected_network}"
            _step(report, f"浏览器资源加载失败提示：{len(network_errors)} 条，均为故意制造的首页生成 503")

            third_party_errors = recorder.third_party_console_errors()
            for item in third_party_errors:
                _step(report, f"第三方 console error（非本站资源）：{item['text'][:90]} @ {item['location'].get('url')}")
            stadium = [item for item in recorder.console if "stadium" in json.dumps(item, ensure_ascii=False)]
            assert not stadium, f"干净 Chromium 中出现了 stadium.js 相关记录：{stadium}"
            _step(report, f"失败网络请求：{len(recorder.failed_requests)} 条（掉线场景预期内）")
        except Exception:
            try:
                SHOTS.mkdir(parents=True, exist_ok=True)
                shot = SHOTS / "magicclass-courses-FAILURE.png"
                page.screenshot(path=str(shot), full_page=False)
                print(f"失败截图：{shot}", file=sys.stderr)
            except Exception:
                pass
            diagnose(page, recorder, "run_checks")
            raise
        finally:
            context.close()
            browser.close()

    return {"report": report, "shots": [str(path) for path in shots]}
