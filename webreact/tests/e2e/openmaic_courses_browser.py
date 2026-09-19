"""OpenMAIC 课程页的**真实浏览器**验收。

与 `interactive-classroom-browser.py` 的区别是这里**不做任何 API route mock**：浏览器
打的是真实的 Vite → FastAPI → openmaic-service 链路，用隔离的测试数据库和测试学生
账号。因此它能发现"单测全绿但真实链路 503"这类问题。

覆盖四件事：
1. 健康链路 —— `GET /api/v1/courses/{id}/workspaces?limit=1` 必须是 200；
2. 运行中掉线 —— 受管服务停掉后点"快速询问"，只出现**局部中文错误**，课程列表与
   已输入的问题原样保留（这是原始故障的反事实：旧代码会把整页替换成错误卡片）；
3. 恢复后重试 —— 服务回来后点"重试"必须成功，且不需要刷新整站；
4. 320/768/1024/1440 四尺寸无横向溢出并留截图。

同时收集 console / pageerror / 失败请求，业务链路上不允许有未处理错误。
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5184")
STUDENT_USERNAME = os.environ.get("E2E_STUDENT_USERNAME", "student_demo")
STUDENT_PASSWORD = os.environ.get("E2E_STUDENT_PASSWORD", "Demo123456")
SHOTS = Path(os.environ.get("E2E_SHOTS_DIR", str(Path(__file__).resolve().parent / "shots")))

VIEWPORTS = [(320, 720, "phone"), (768, 900, "tablet"), (1024, 900, "laptop"), (1440, 900, "desktop")]

# 站内 console 允许出现的信息级提示（不含错误）。
BENIGN_CONSOLE = (
    "Download the React DevTools",
    "[api] 5xx",  # 掉线场景下 api.js 自己写的开发诊断
)

# Chromium 对非 2xx 响应自动写的资源加载提示前缀。它是浏览器行为，不是站点脚本错误，
# 但必须逐条核对 URL —— 掉线场景故意制造的 503 应该出现，其他任何一条都不允许。
NETWORK_MESSAGE_PREFIX = "Failed to load resource:"


class Recorder:
    """收集 console / pageerror / 失败请求，供最终断言与报告使用。"""

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
        page.on("requestfailed", lambda request: self.failed_requests.append({
            "url": request.url,
            "method": request.method,
            "failure": (request.failure or {}).get("errorText", ""),
        }))
        page.on("response", lambda response: self.responses.append({
            "url": response.url,
            "status": response.status,
        }))

    def status_of(self, fragment: str) -> int | None:
        for item in reversed(self.responses):
            if fragment in item["url"]:
                return item["status"]
        return None

    def await_status(self, page, fragment: str, timeout: float = 8.0) -> int | None:
        """等某条响应落到记录里。

        `page.on("response")` 是异步回调：断言紧跟在点击之后读取会偶发读空，
        那会把"没读到"误报成"请求失败"。这里轮询到超时为止。
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self.status_of(fragment)
            if status is not None:
                return status
            page.wait_for_timeout(120)
        return None

    def script_console_errors(self) -> list[dict]:
        """站点脚本自己抛出的 console error —— 这一类才是缺陷。

        必须把 Chromium 自带的资源加载提示排除掉：非 2xx 响应会让浏览器自动写一条
        "Failed to load resource"，而掉线场景里我们**故意**让 workspaces 返回 503，
        它必然出现。把它当成站点缺陷会让这个断言永远为红，从而被顺手放宽成"忽略所有
        console error"——那才是真正危险的。
        """
        out = []
        for item in self.console:
            if item["type"] != "error":
                continue
            if any(marker in item["text"] for marker in BENIGN_CONSOLE):
                continue
            if item["text"].startswith(NETWORK_MESSAGE_PREFIX):
                continue
            out.append(item)
        return out

    def network_console_errors(self) -> list[dict]:
        """浏览器对非 2xx 响应自动写的资源加载提示（逐条核对 URL 用）。"""
        return [item for item in self.console
                if item["type"] == "error" and item["text"].startswith(NETWORK_MESSAGE_PREFIX)]

    def third_party_console_errors(self) -> list[dict]:
        """来自非本站资源的 console error —— 这类通常由浏览器扩展注入。"""
        return [item for item in self.script_console_errors()
                if item["location"].get("url") and not item["location"]["url"].startswith(self.base_url)]

    def third_party_failed_requests(self) -> list[dict]:
        return [item for item in self.failed_requests if not item["url"].startswith(self.base_url)]


def _step(report: list[str], text: str) -> None:
    print(f"  · {text}")
    report.append(text)


def diagnose(page, recorder: Recorder, label: str) -> None:
    """失败现场取证。

    超时本身不说明任何事：可能是点击没生效、可能是局部错误挡住了跳转、也可能是
    接口返回了别的状态码。这里把当时能看到的全部状态打出来，避免把"没读到"
    误判成"请求失败"，也避免为了一个原因再跑一轮。
    """
    print(f"\n--- 失败现场（{label}）---", file=sys.stderr)
    try:
        print(f"当前 URL：{page.url}", file=sys.stderr)
    except Exception:
        pass
    for selector, name in (
        (".openmaic-ask__error", "局部错误区"),
        (".openmaic-ask__hint", "能力提示"),
        (".state-card.error-state", "整页错误卡片"),
    ):
        try:
            locator = page.locator(selector)
            if locator.count():
                print(f"{name}：{locator.first.inner_text().strip()[:300]}", file=sys.stderr)
            else:
                print(f"{name}：不存在", file=sys.stderr)
        except Exception as exc:
            print(f"{name}：读取失败（{exc}）", file=sys.stderr)
    try:
        submit = page.locator('form.openmaic-ask button[type="submit"]')
        print(f"提交按钮：count={submit.count()} disabled={submit.first.is_disabled() if submit.count() else 'n/a'}", file=sys.stderr)
        textarea = page.locator("textarea.openmaic-ask__input")
        print(f"输入框：value={textarea.first.input_value()[:80]!r}", file=sys.stderr)
        select = page.locator("select.openmaic-ask__select")
        print(f"课程下拉：value={select.first.input_value()!r}", file=sys.stderr)
    except Exception as exc:
        print(f"表单状态读取失败（{exc}）", file=sys.stderr)
    print(f"最近 25 条响应：", file=sys.stderr)
    for item in recorder.responses[-25:]:
        print(f"    {item['status']} {item['url'][:160]}", file=sys.stderr)
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


def open_courses(page, report: list[str]) -> str:
    page.goto(f"{BASE}/courses", wait_until="domcontentloaded")
    page.wait_for_selector("select.openmaic-ask__select", timeout=20000)
    # 真实课程列表：直接从下拉框读，而不是写死 id。
    options = page.locator("select.openmaic-ask__select option").all()
    labels = [option.inner_text() for option in options if option.get_attribute("value")]
    if not labels:
        raise AssertionError("课程下拉框没有任何真实课程")
    course_id = page.locator("select.openmaic-ask__select").input_value()
    if not course_id:
        # 默认选中项为空时显式选第一门。
        course_id = options[1].get_attribute("value")
        page.locator("select.openmaic-ask__select").select_option(course_id)
    _step(report, f"/courses 加载了 {len(labels)} 门真实课程，当前选择 {course_id}")
    return course_id


def check_viewports(page, recorder: Recorder, report: list[str]) -> list[Path]:
    shots: list[Path] = []
    SHOTS.mkdir(parents=True, exist_ok=True)
    for width, height, label in VIEWPORTS:
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(320)
        overflow = page.evaluate(
            "() => ({ scrollWidth: document.documentElement.scrollWidth, inner: window.innerWidth })"
        )
        assert overflow["scrollWidth"] <= overflow["inner"] + 1, (
            f"{width}px 出现横向溢出：{overflow['scrollWidth']} > {overflow['inner']}"
        )
        # 焦点元素不得被挤出视口。
        box = page.locator("form.openmaic-ask").bounding_box()
        assert box, f"{width}px 找不到输入工作区"
        assert box["x"] >= -1 and box["x"] + box["width"] <= width + 1, (
            f"{width}px 输入工作区超出视口：x={box['x']} w={box['width']}"
        )
        shot = SHOTS / f"openmaic-courses-{label}-{width}x{height}.png"
        page.screenshot(path=str(shot), full_page=False)
        shots.append(shot)
        _step(report, f"{width}×{height} 无横向溢出，输入工作区在视口内 → {shot.name}")
    # 再补一张整页长图：折叠区（我的课程 / 更多学习工具）在首屏之外，
    # 只看视口截图无法判断完整层级是否成立。
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(320)
    full = SHOTS / "openmaic-courses-fullpage-1440.png"
    page.screenshot(path=str(full), full_page=True)
    shots.append(full)
    _step(report, f"整页长图（含折叠区层级）→ {full.name}")

    # 这个壳层把滚动放在内层容器里，document 本身不滚动：`full_page=True` 只能
    # 展开 document 的高度，抓不到内层滚出去的部分。所以显式滚到底再拍一张，
    # 否则"折叠区到底长什么样"只能靠猜。
    geometry = page.evaluate(
        """() => {
            const pick = (sel) => {
                const el = document.querySelector(sel);
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return { top: Math.round(r.top + window.scrollY), height: Math.round(r.height) };
            };
            let scroller = null;
            for (let el = document.querySelector('.openmaic-home'); el; el = el.parentElement) {
                const style = getComputedStyle(el);
                if (/(auto|scroll)/.test(style.overflowY) && el.scrollHeight > el.clientHeight + 4) {
                    scroller = el; break;
                }
            }
            return {
                blocks: {
                    ask: pick('.openmaic-command-panel'),
                    recent: pick('.openmaic-recent-panel'),
                    secondary: pick('.openmaic-secondary'),
                    rail: pick('.openmaic-home__rail'),
                },
                railItems: document.querySelectorAll('.openmaic-course-rail__item').length,
                tabCount: document.querySelectorAll('.openmaic-tabs [role=tab]').length,
                doc: {
                    scrollHeight: document.documentElement.scrollHeight,
                    clientHeight: document.documentElement.clientHeight,
                    bodyScrollHeight: document.body.scrollHeight,
                    innerHeight: window.innerHeight,
                },
                chain: (() => {
                    const out = [];
                    for (let el = document.querySelector('.openmaic-home'); el; el = el.parentElement) {
                        const s = getComputedStyle(el);
                        out.push({
                            tag: el.tagName.toLowerCase(),
                            cls: String(el.className || '').slice(0, 60),
                            overflowY: s.overflowY,
                            height: s.height,
                            clientHeight: el.clientHeight,
                            scrollHeight: el.scrollHeight,
                        });
                    }
                    return out;
                })(),
                scroller: scroller ? { cls: scroller.className, scrollHeight: scroller.scrollHeight, clientHeight: scroller.clientHeight } : null,
            };
        }"""
    )
    _step(report, f"文档高度：scrollHeight={geometry['doc']['scrollHeight']} "
                 f"clientHeight={geometry['doc']['clientHeight']} body={geometry['doc']['bodyScrollHeight']} "
                 f"innerHeight={geometry['doc']['innerHeight']}")
    for item in geometry["chain"]:
        _step(report, f"祖先链 {item['tag']}.{item['cls']} overflowY={item['overflowY']} "
                     f"height={item['height']} client={item['clientHeight']} scroll={item['scrollHeight']}")
    for name, box in geometry["blocks"].items():
        assert box is not None, f"折叠区缺少区块：{name}"
        _step(report, f"区块 {name}：top={box['top']} height={box['height']}")
    _step(report, f"课程列表项 {geometry['railItems']} 条；次级标签页 {geometry['tabCount']} 个")

    # 关键断言：折叠区必须**可达**。只断言"存在于 DOM"是不够的——框架 overflow:hidden
    # 会把超出部分裁掉，元素仍在 DOM 里、locator.count() 照样数得到，但用户永远看不到。
    # 之前 我的课程(31 门≈2479px) 与 更多学习工具 就是这样整块不可达而没被发现的。
    for selector, name in ((".openmaic-secondary", "更多学习工具"), (".openmaic-home__rail", "我的课程")):
        locator = page.locator(selector)
        assert locator.count(), f"{name} 不在 DOM 中"
        locator.first.scroll_into_view_if_needed(timeout=8000)
        page.wait_for_timeout(200)
        assert locator.first.is_visible(), f"{name} 不可见"
        box = locator.first.bounding_box()
        assert box, f"{name} 没有布局盒子"
        visible = min(box["height"], 40)
        assert -1 <= box["y"] and box["y"] + visible <= 900 + 1, (
            f"{name} 滚入视口后仍不可见：y={box['y']} height={box['height']}（被框架裁剪）"
        )
        _step(report, f"折叠区可达：{name}（y={round(box['y'])}，height={round(box['height'])}）")
        if selector == ".openmaic-secondary":
            # 次级导航（能力驱动的标签页）也要有一张图，否则"折叠区长什么样"没有证据。
            mid = SHOTS / "openmaic-courses-secondary-1440.png"
            page.screenshot(path=str(mid), full_page=False)
            shots.append(mid)
            _step(report, f"次级导航截图 → {mid.name}")

            # 工作台条目的操作区：3 列栅格里塞进 6 个子节点时，操作会被自动放进隐式
            # 第二行——第一列只有 32px，"进入工作台"会被压成每行一个字。这类"能渲染
            # 但不可用"的破版必须由几何断言兜住。
            actions = page.locator(".openmaic-workspace-item__actions")
            if actions.count():
                box = actions.first.bounding_box()
                assert box and box["width"] >= 140, f"工作台操作区被压扁：width={box and box['width']}"
                assert box["height"] <= 56, f"工作台操作区折成多行（疑似竖排文字）：height={box['height']}"
                _step(report, f"工作台操作区布局正常：width={round(box['width'])} height={round(box['height'])}")

    if geometry["scroller"]:
        _step(report, f"内层滚动容器：{geometry['scroller']['cls']} "
                     f"scrollHeight={geometry['scroller']['scrollHeight']} clientHeight={geometry['scroller']['clientHeight']}")
        page.evaluate(
            """() => {
                for (let el = document.querySelector('.openmaic-home'); el; el = el.parentElement) {
                    const style = getComputedStyle(el);
                    if (/(auto|scroll)/.test(style.overflowY) && el.scrollHeight > el.clientHeight + 4) {
                        el.scrollTop = el.scrollHeight; break;
                    }
                }
            }"""
        )
        page.wait_for_timeout(400)
        folded = SHOTS / "openmaic-courses-folded-1440.png"
        page.screenshot(path=str(folded), full_page=False)
        shots.append(folded)
        _step(report, f"折叠区截图 → {folded.name}")
    return shots


def run_checks(service_control) -> dict:
    """执行全部浏览器检查。`service_control` 提供 stop()/start() 控制受管服务。"""
    report: list[str] = []
    recorder = Recorder(BASE)
    shots: list[Path] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = context.new_page()
        recorder.attach(page)

        try:
            print("步骤 1：真实登录并进入 /courses")
            login(page, report)
            course_id = open_courses(page, report)

            print("步骤 2：健康链路 —— 快速询问应得到 200 而不是 503")
            question = "进程和线程有什么区别？"
            page.locator("textarea.openmaic-ask__input").fill(question)
            recorder.responses.clear()
            page.locator('form.openmaic-ask button[type="submit"]').click()
            page.wait_for_url("**/counselor**", timeout=20000)
            list_status = recorder.await_status(page, f"/courses/{course_id}/workspaces?limit=1")
            assert list_status == 200, f"workspaces?limit=1 返回 {list_status}，期望 200"
            _step(report, f"GET /api/v1/courses/{course_id}/workspaces?limit=1 → HTTP {list_status}")

            current = page.url
            assert "course=" in current and "prompt=" in current, f"深链缺少课程或问题：{current}"
            assert "workspace=" in current, "能力可用时应绑定真实工作台"
            _step(report, f"跳转到课程辅导，URL 携带 course / workspace / prompt：{current.split('?')[-1][:120]}")
            expect(page.locator(".counselor-course-context")).to_be_visible(timeout=15000)
            _step(report, "辅导页显示课程上下文横幅（含工作台绑定）")

            print("步骤 3：刷新后课程上下文可恢复")
            page.reload(wait_until="domcontentloaded")
            expect(page.locator(".counselor-course-context")).to_be_visible(timeout=15000)
            _step(report, "刷新 /counselor 后课程上下文仍在（状态来自 URL，不依赖内存）")

            print("步骤 4：运行中掉线 —— 局部降级，课程页不被替换")
            page.goto(f"{BASE}/courses", wait_until="domcontentloaded")
            page.wait_for_selector("select.openmaic-ask__select", timeout=20000)
            ready_note = page.locator(".openmaic-ask__hint").inner_text()
            assert "就绪" in ready_note, f"服务在线时状态提示不诚实：{ready_note}"
            _step(report, f"服务在线时提示：{ready_note.strip()}")

            service_control.stop()
            _step(report, "已停掉 openmaic-service（4010），页面保持已加载状态")
            page.locator("textarea.openmaic-ask__input").fill(question)
            rail_before = page.locator(".openmaic-course-rail__item").count()
            recorder.responses.clear()
            page.locator('form.openmaic-ask button[type="submit"]').click()
            expect(page.locator(".openmaic-ask__error")).to_be_visible(timeout=20000)

            failed_status = recorder.await_status(page, f"/courses/{course_id}/workspaces?limit=1")
            assert failed_status == 503, f"掉线时应为 503，实际 {failed_status}"
            _step(report, f"GET /api/v1/courses/{course_id}/workspaces?limit=1 → HTTP {failed_status}")

            error_text = page.locator(".openmaic-ask__error").inner_text()
            assert "Request failed with status code" not in error_text, f"把 Axios 英文原文给了用户：{error_text}"
            assert any(ch in error_text for ch in "请稍后未启用不可用"), f"错误文案不是中文可操作信息：{error_text}"
            _step(report, f"局部中文错误：{error_text.splitlines()[0].strip()}")

            assert page.url.startswith(f"{BASE}/courses"), f"失败后不应离开课程页：{page.url}"
            assert page.locator(".state-card.error-state").count() == 0, "整页错误卡片出现了"
            rail_after = page.locator(".openmaic-course-rail__item").count()
            assert rail_after == rail_before and rail_after > 0, "课程列表被替换掉了"
            _step(report, f"课程列表仍在（{rail_after} 门课程），未出现整页错误卡片")
            assert page.locator("textarea.openmaic-ask__input").input_value() == question, "已输入的问题丢失"
            _step(report, "已输入的问题与所选课程原样保留")

            print("步骤 5：服务故障时其他课程功能仍可用")
            recorder.responses.clear()
            page.goto(f"{BASE}/courses/{course_id}", wait_until="domcontentloaded")
            page.wait_for_selector("main", timeout=20000)
            detail_status = recorder.await_status(page, f"/api/v1/courses/{course_id}", timeout=4.0)
            assert page.locator("main").count() > 0, "课程详情页没有渲染"
            _step(report, f"课程详情 /courses/{course_id} 仍可打开（GET /api/v1/courses/{course_id} → {detail_status}）")

            print("步骤 6：恢复服务后重试，无需刷新整站")
            # 关键顺序：页面必须在**服务在线时**加载，此时 fusion=ready，点击会去绑定
            # 工作台；随后才停服务，让这一次点击撞上 503。若在服务已停时加载页面，
            # 页面会正确地走"不绑定工作台、直接进入课程辅导"的降级路径——那是另一种
            # 正确行为，拿它来断言"出现局部错误"就是测错了东西。
            service_control.start()
            page.goto(f"{BASE}/courses", wait_until="domcontentloaded")
            page.wait_for_selector("select.openmaic-ask__select", timeout=20000)
            page.locator("textarea.openmaic-ask__input").fill(question)
            service_control.stop()
            page.locator('form.openmaic-ask button[type="submit"]').click()
            expect(page.locator(".openmaic-ask__error")).to_be_visible(timeout=20000)
            _step(report, "服务在线时加载、点击瞬间掉线 → 只出现局部错误，未跳转")

            service_control.start()
            _step(report, "已恢复 openmaic-service，点击局部错误里的「重试」")
            recorder.responses.clear()
            page.locator('.openmaic-ask__error-actions button:has-text("重试")').click()
            page.wait_for_url("**/counselor**", timeout=25000)
            retry_status = recorder.await_status(page, f"/courses/{course_id}/workspaces?limit=1")
            assert retry_status == 200, f"重试后 workspaces 仍为 {retry_status}"
            _step(report, f"重试成功：GET /api/v1/courses/{course_id}/workspaces?limit=1 → HTTP {retry_status}，未刷新整站")

            print("步骤 7：四尺寸截图与溢出检查")
            page.goto(f"{BASE}/courses", wait_until="domcontentloaded")
            page.wait_for_selector("select.openmaic-ask__select", timeout=20000)
            shots = check_viewports(page, recorder, report)

            print("步骤 8：console / pageerror / 失败请求")
            script_errors = recorder.script_console_errors()
            third_party_errors = recorder.third_party_console_errors()
            assert not recorder.page_errors, f"出现未捕获的页面异常：{recorder.page_errors}"
            _step(report, "pageerror：0 条（业务链路上没有未处理异常）")
            assert not script_errors, f"站点脚本出现 console error：{script_errors}"
            _step(report, "站点脚本 console error：0 条")

            # 资源加载失败提示逐条核对：只允许掉线场景里我们故意制造的那条 503。
            deliberate = f"/courses/{course_id}/workspaces?limit=1"
            network_errors = recorder.network_console_errors()
            unexpected = [item for item in network_errors
                          if deliberate not in (item["location"].get("url") or "")]
            assert not unexpected, f"出现了预期之外的资源加载失败：{unexpected}"
            _step(report, f"浏览器资源加载失败提示：{len(network_errors)} 条，全部是掉线场景故意制造的 workspaces 503")

            if third_party_errors:
                for item in third_party_errors:
                    _step(report, f"第三方 console error（非本站资源）：{item['text'][:90]} @ {item['location'].get('url')}")

            # 图一里那条 `stadium.js:1 Error` 的来源判定：在干净 Chromium（无扩展）里
            # 复现不了就说明是扩展注入，不是本站资源。
            stadium = [item for item in recorder.console if "stadium" in json.dumps(item, ensure_ascii=False)]
            assert not stadium, f"干净 Chromium 中出现了 stadium.js 相关记录：{stadium}"
            _step(report, "干净 Chromium 中 stadium.js 相关 console 记录：0 条（判定为浏览器扩展注入，非本站资源）")

            _step(report, f"失败网络请求：{len(recorder.failed_requests)} 条（掉线场景预期内）")
        except Exception:
            # 任何一步失败都先把现场留下来：截图 + 状态转储。只有拿到现场，
            # 报告里的"失败原因"才是查出来的，不是猜出来的。
            try:
                SHOTS.mkdir(parents=True, exist_ok=True)
                shot = SHOTS / "openmaic-courses-FAILURE.png"
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
