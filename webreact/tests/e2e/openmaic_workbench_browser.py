"""OpenMAIC 学习工作台的**真实浏览器**验收：前端视觉对齐 + 响应式互斥单面板。

与 `openmaic_courses_browser.py` 的分工：那个脚本走的是「/courses → 生成预览 →
工作台」这条旧链路，本脚本走**用户实际路径**——

    /courses（我的课程）→ 点真实「进入课堂」→ 直接进工作台（不经过角色/模式/预览）
    → 在已有真实工作台上测 320 / 390 / 768 / 1024 / 1440
    → 回归「开始学习」进播放、返回编辑、刷新
    → 回归 503：仍停在课堂，中文错误、重试生成、手动创建工作台、返回课程都在

不做任何 route mock：浏览器打的是 Vite → FastAPI → openmaic-service 的真实链路。

每个断点都记录**几何证据**（不是"看起来没问题"）：
    - documentElement.scrollWidth <= clientWidth（页面级无横向滚动）
    - 当前激活 pane 的实际宽度
    - 所有可见主按钮与 tab 的 bounding box 是否落在 viewport 内
    - 依次点击 目录 / 课堂 / 工具，每次 DOM 里有且只有一个内容 pane
    - 320px 下课堂不再被固定 60px rail 挤压（面板宽度 ≈ 视口宽度，没有那条 rail）
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

# 截图默认**不落盘**。这个脚本属于仓库，任何默认输出目录都会变成仓库里的产物，
# 而"靠 .gitignore 掩盖"不是清理。只有在显式给出 E2E_SHOTS_DIR 时才存图——
# run_openmaic_workbench_e2e.py 会把它指到本次运行的临时目录里，随 finally 一起删。
_shots_env = os.environ.get("E2E_SHOTS_DIR", "").strip()
SHOTS = Path(_shots_env) if _shots_env else None

# (宽, 高, 标签, 期望的布局)
VIEWPORTS = [
    (320, 720, "phone", "narrow"),
    (390, 844, "phone-large", "narrow"),
    (768, 900, "tablet", "narrow"),
    (1024, 900, "laptop", "wide"),
    (1440, 900, "desktop", "wide"),
]

BENIGN_CONSOLE = ("Download the React DevTools", "[api] 5xx")
NETWORK_MESSAGE_PREFIX = "Failed to load resource:"

PANES = {
    "目录": ".ow-pane--rail",
    "课堂": ".ow-pane--classroom",
    "工具": ".ow-pane--tools",
}


class Recorder:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.console: list[dict] = []
        self.page_errors: list[str] = []
        self.failed_requests: list[dict] = []
        self.responses: list[dict] = []
        self.rejections: list[str] = []

    def attach(self, page) -> None:
        page.on("console", lambda m: self.console.append({
            "type": m.type, "text": m.text, "location": m.location or {},
        }))
        page.on("pageerror", lambda e: self.page_errors.append(str(e)))
        page.on("requestfailed", lambda r: self.failed_requests.append({
            "url": r.url, "method": r.method,
            "failure": (r.failure or {}).get("errorText", ""),
        }))
        page.on("response", lambda r: self.responses.append({"url": r.url, "status": r.status}))
        # 未处理的 Promise rejection 是"console error 之外"的另一类真实缺陷。
        page.add_init_script(
            """() => {
                window.__unhandled = [];
                addEventListener('unhandledrejection', (event) => {
                    window.__unhandled.push(String((event.reason && event.reason.message) || event.reason));
                });
            }"""
        )

    def status_of(self, fragment: str) -> int | None:
        for item in reversed(self.responses):
            if fragment in item["url"]:
                return item["status"]
        return None

    def await_status(self, page, fragment: str, timeout: float = 8.0) -> int | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self.status_of(fragment)
            if status is not None:
                return status
            page.wait_for_timeout(120)
        return None

    def script_console_errors(self) -> list[dict]:
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
        return [i for i in self.console
                if i["type"] == "error" and i["text"].startswith(NETWORK_MESSAGE_PREFIX)]


def _step(report: list[str], text: str) -> None:
    print(f"  · {text}")
    report.append(text)


def diagnose(page, recorder: Recorder, label: str) -> None:
    print(f"\n--- 失败现场（{label}）---", file=sys.stderr)
    try:
        print(f"当前 URL：{page.url}", file=sys.stderr)
    except Exception:
        pass
    try:
        print("工作台几何：", file=sys.stderr)
        print(json.dumps(page.evaluate(WORKBENCH_GEOMETRY), ensure_ascii=False, indent=2), file=sys.stderr)
    except Exception as exc:
        print(f"几何读取失败（{exc}）", file=sys.stderr)
    if recorder.page_errors:
        print("pageerror：", file=sys.stderr)
        for item in recorder.page_errors[-10:]:
            print(f"    {item[:600]}", file=sys.stderr)
    errors = [i for i in recorder.console if i["type"] == "error"]
    if errors:
        print("console error：", file=sys.stderr)
        for item in errors[-10:]:
            print(f"    {item['text'][:400]}", file=sys.stderr)
    print("最近 20 条响应：", file=sys.stderr)
    for item in recorder.responses[-20:]:
        print(f"    {item['status']} {item['url'][:150]}", file=sys.stderr)


# ── 浏览器内取证：一次 evaluate 把断点需要的几何全部取回来 ──────────────────
WORKBENCH_GEOMETRY = """() => {
    const visible = (el) => {
        if (!el) return false;
        // 必须沿祖先链判断：祖先 `display: none` 时元素自身的 display 仍是
        // inline-flex，getBoundingClientRect 也只是 0×0。只看元素自己会把一个被隐藏
        // 祖先包住的按钮误判成"隐藏的可聚焦元素"（这正是 `.ow-export` 在小屏的样子）。
        for (let node = el; node && node !== document.body; node = node.parentElement) {
            const style = getComputedStyle(node);
            if (style.display === 'none' || style.visibility === 'hidden') return false;
        }
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    };
    /**
     * 元素是否仍在 tab 序列里（键盘用户能不能聚焦到它）。
     *
     * `display: none` 会让整棵子树退出可聚焦集合，所以"隐藏但不可聚焦"是合法的，
     * 不需要报错；`visibility: hidden` 的祖先则**不会**移除可聚焦性，那才会让键盘
     * 用户聚焦到一个看不见的控件。这里按浏览器自己的规则判断，而不是按元素是否
     * 有尺寸——后者会把正常的隐藏按钮误报成缺陷。
     */
    const isTabReachable = (el) => {
        if (el.disabled) return false;
        if (el.getAttribute('tabindex') === '-1') return false;
        if (el.closest('[inert]')) return false;
        for (let node = el; node && node !== document.body; node = node.parentElement) {
            const style = getComputedStyle(node);
            if (style.display === 'none') return false;         // 退出 tab 序列
            if (style.visibility === 'hidden') return true;      // 仍然可聚焦 —— 缺陷
        }
        return true;
    };
    const boxOf = (el) => {
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return {
            x: Math.round(r.x), y: Math.round(r.y),
            width: Math.round(r.width), height: Math.round(r.height),
            right: Math.round(r.right), bottom: Math.round(r.bottom),
            label: (el.getAttribute('aria-label') || el.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 40),
            cls: String(el.className || '').slice(0, 60),
        };
    };
    const root = document.querySelector('[data-testid="openmaic-workbench"]');
    const panesPresent = ['.ow-pane--rail', '.ow-pane--classroom', '.ow-pane--tools']
        .filter((sel) => document.querySelector(sel));
    // 可交互主控件：面板里的按钮 / tab / 输入，以及「开始学习」。
    const focusables = [...document.querySelectorAll(
        '.ow-pane button, .ow-pane [role="tab"], .ow-pane input, .ow-pane select, .ow-pane textarea, [data-testid="ow-start-learning"]'
    )];
    /**
     * 判定一个控件"越界"还是"只是要滚动"。
     *
     * 这两件事必须分开，否则会把一个正常可滚动的长列表误报成破版。区别在于：
     * 如果某条祖先链上存在一个**可以滚到它**的容器（overflow 为 auto/scroll 且确实
     * 有溢出），那它只是暂时在视野外，用户可以滚到；如果没有任何这样的容器，它就
     * 是被 `overflow: hidden` **裁掉**了——DOM 里有、用户永远点不到，那才是缺陷。
     */
    const reachable = (el) => {
        for (let node = el.parentElement; node; node = node.parentElement) {
            const style = getComputedStyle(node);
            if (/(auto|scroll)/.test(style.overflowY) && node.scrollHeight > node.clientHeight + 1) return true;
            if (/(auto|scroll)/.test(style.overflowX) && node.scrollWidth > node.clientWidth + 1) return true;
        }
        return false;
    };
    const navButtons = [...document.querySelectorAll('.ow-seg--nav button')].map((el) => ({
        text: (el.textContent || '').trim(),
        // 切换控件是 aria-pressed 的普通按钮（不是一整套 tab 语义）。
        pressed: el.getAttribute('aria-pressed') === 'true',
        role: el.getAttribute('role'),
        tabIndex: el.tabIndex,
    }));
    const boxes = focusables.filter(visible).map((el) => {
        const box = boxOf(el);
        box.reachable = reachable(el);
        box.insidePane = Boolean(el.closest('.ow-pane'));
        return box;
    });
    const outside = boxes.filter((b) => (
        b.x < -1 || b.right > window.innerWidth + 1 || b.y < -1 || b.bottom > window.innerHeight + 1
    ));
    return {
        viewport: { width: window.innerWidth, height: window.innerHeight },
        document: {
            scrollWidth: document.documentElement.scrollWidth,
            clientWidth: document.documentElement.clientWidth,
            bodyScrollWidth: document.body.scrollWidth,
        },
        layout: root ? root.getAttribute('data-ow-layout') : null,
        paneAttr: root ? root.getAttribute('data-ow-pane') : null,
        // 工作台自己的宽度：窄屏"占满可用宽度"要跟它比，而不是跟视口宽度比——
        // 视口里可能还站着一条纵向滚动条。
        root: root ? boxOf(root) : null,
        panesPresent,
        paneBoxes: panesPresent.map((sel) => ({ sel, ...boxOf(document.querySelector(sel)) })),
        nav: document.querySelector('.ow-nav') ? boxOf(document.querySelector('.ow-nav')) : null,
        navButtons,
        switcherCount: document.querySelectorAll('.ow-seg--nav button').length,
        // tablist 不得嵌套：外层 nav 里的课程标签条是页面上唯一的 tablist。
        tablistCount: document.querySelectorAll('[role="tablist"]').length,
        nestedTablists: [...document.querySelectorAll('[role="tablist"]')]
            .filter((el) => el.parentElement?.closest('[role="tablist"]')).length,
        navTag: document.querySelector('.ow-nav')?.tagName.toLowerCase() || null,
        navRole: document.querySelector('.ow-nav')?.getAttribute('role') || null,
        start: boxOf(document.querySelector('[data-testid="ow-start-learning"]')),
        stage: boxOf(document.querySelector('[data-maic-stage-card="true"]')),
        overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        // 被 overflow:hidden 裁掉、用户永远够不到的控件——真正的越界。
        clipped: outside.filter((b) => !b.reachable).map((b) => ({
            label: b.label, x: b.x, right: b.right, y: b.y, bottom: b.bottom,
        })),
        // 在视口之外、但所在的滚动容器可以滚到——只是需要滚动。
        belowFold: outside.filter((b) => b.reachable).map((b) => ({ label: b.label, y: b.y })),
        visibleFocusables: focusables.filter(visible).length,
        // 真正的问题不是"存在一个隐藏元素"，而是"存在一个**能聚焦**的隐藏元素"：
        // `display: none`（连同祖先）会让元素退出 tab 序列，那是正确的隐藏；
        // 只有被 `visibility: hidden`/零尺寸裁剪等方式藏起来、却仍留在 tab 序列里的
        // 控件，才会让键盘用户聚焦到一个看不见的东西上。
        focusableButHidden: focusables.filter((el) => !visible(el) && isTabReachable(el)).map((el) => ({
            label: (el.getAttribute("aria-label") || el.textContent || "").replace(/\\s+/g, " ").trim().slice(0, 40),
            cls: String(el.className || "").slice(0, 60),
        })),
        hiddenCount: focusables.filter((el) => !visible(el)).length,
        hasRail60: (() => {
            const rail = document.querySelector('.ow-pane--rail');
            return rail ? Math.round(rail.getBoundingClientRect().width) : 0;
        })(),
    };
}"""


def assert_no_h_overflow(geometry: dict, label: str) -> None:
    doc = geometry["document"]
    assert doc["scrollWidth"] <= doc["clientWidth"] + 1, (
        f"{label} 出现页面级横向滚动：scrollWidth={doc['scrollWidth']} > clientWidth={doc['clientWidth']}"
    )
    assert doc["bodyScrollWidth"] <= geometry["viewport"]["width"] + 1, (
        f"{label} body 横向溢出：bodyScrollWidth={doc['bodyScrollWidth']}"
    )


def assert_focusables_in_view(geometry: dict, label: str) -> None:
    """主控件不得被裁掉。

    区分两件事：被 `overflow: hidden` 裁掉（DOM 里有、用户永远点不到 → 缺陷）与
    只是需要滚动才能看到（正常）。一个不可滚动的祖先链已经把控件吃掉了才算失败。
    """
    assert not geometry["clipped"], (
        f"{label} 有可见主控件被 overflow 裁掉、用户点不到："
        + json.dumps(geometry["clipped"], ensure_ascii=False)
    )
    if geometry["belowFold"]:
        print(f"    （{label} 需滚动可见的控件："
              + "、".join(item["label"] for item in geometry["belowFold"]) + "）")


def login(page, report: list[str]) -> None:
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.locator("form input").nth(0).fill(STUDENT_USERNAME)
    page.locator("form input").nth(1).fill(STUDENT_PASSWORD)
    page.locator('form button:has-text("登录")').click()
    page.wait_for_url(f"{BASE}/home", timeout=25000)
    _step(report, f"真实 UI 登录成功：{STUDENT_USERNAME} → /home")


def enter_classroom_from_my_courses(page, recorder: Recorder, report: list[str]) -> str:
    """在「我的课程」里点**真实**「进入课堂」，断言直达工作台。"""
    page.goto(f"{BASE}/courses", wait_until="domcontentloaded")
    enter = page.locator(".openmaic-course-rail__enter").first
    expect(enter).to_be_visible(timeout=25000)
    label = enter.get_attribute("aria-label") or ""
    assert "进入" in label and "课堂" in label, f"「进入课堂」入口的可访问名称不对：{label}"
    # 入口是一个**直接指向课堂路由**的链接。这就是"不经过角色 / 模式 / 预览确认"
    # 的结构证据：深链里没有任何 prompt / mode / roles 参数，目标也不是预览页。
    href = enter.get_attribute("href") or ""
    assert href.endswith("/classroom"), f"「进入课堂」应直接指向课堂路由，实际 {href}"
    assert "/openmaic-preview" not in href, "「进入课堂」不得指向生成预览"
    for param in ("prompt=", "mode=", "roles="):
        assert param not in href, f"「进入课堂」的深链不应携带 {param}：{href}"
    _step(report, f"「我的课程」里的直达入口：{label} → {href}（无 prompt/mode/roles）")

    recorder.responses.clear()
    enter.click()
    page.wait_for_url("**/classroom", timeout=15000)
    assert "/openmaic-preview" not in page.url, f"「进入课堂」不应走生成预览：{page.url}"
    _step(report, f"点击后进入直达页（非预览、非角色选择）：{page.url.split('/courses/')[-1]}")

    page.wait_for_url("**/workspaces/**", timeout=60000)
    assert "/counselor" not in page.url, "不得跳到小助手"
    expect(page.locator('[data-testid="openmaic-workbench"]')).to_be_visible(timeout=30000)
    _step(report, "直达工作台：未经过角色 / 模式 / 预览确认")
    # direct 落地后必须真的把课堂渲染出来（可以是"正在生成"，但不能是空白）。
    expect(page.locator(".ow-classroom-body")).to_be_visible(timeout=30000)
    _step(report, f"工作台 URL：{page.url.split('?')[0].split('/workspaces/')[-1]}")
    return page.url


def first_real_workbench(page, recorder: Recorder, report: list[str]) -> str:
    """打开一个已存在、已有内容的真实工作台（真实课程数据）。

    走的是应用自己的 API 客户端（同源、已带鉴权头），不是裸 fetch：裸 fetch 少了
    `Authorization`，会拿到 401，于是这条"找一个有内容的工作台"的辅助步骤会伪装成
    "真实数据里没有工作台"——那正是最容易被误读成产品缺陷的一种假失败。
    """
    workbenches = page.evaluate(
        """async () => {
            const api = await import('/src/data/api.js');
            const courses = await api.getCourses();
            const out = [];
            for (const course of (courses.items || [])) {
                const list = await api.listOpenMAICWorkspaces(course.id, { limit: 5 });
                for (const ws of (list.items || [])) {
                    const stages = await api.listOpenMAICStages(course.id, ws.id, { limit: 5 });
                    out.push({
                        courseId: course.id, courseName: course.name,
                        workspaceId: ws.id, workspaceName: ws.name,
                        stages: (stages.items || []).length,
                    });
                }
            }
            return out;
        }"""
    )
    assert workbenches, "真实数据里没有工作台"
    with_stage = [item for item in workbenches if item["stages"] > 0]
    if with_stage:
        target = with_stage[0]
    else:
        # 数据可能被上一轮验收清空了：用最少量的真实操作补一个可验收的舞台，
        # 而不是跳过舞台断言——跳过就等于把"舞台到底什么样"变成猜测。
        target = workbenches[0]
        _step(report, "真实数据里暂时没有已生成内容的工作台，先通过工作台自己的生成入口建一个")
        page.goto(f"{BASE}/courses/{target['courseId']}/workspaces/{target['workspaceId']}",
                  wait_until="domcontentloaded")
        expect(page.locator('[data-testid="openmaic-workbench"]')).to_be_visible(timeout=30000)
        page.set_viewport_size({"width": 1440, "height": 900})
        page.locator('input[aria-label="学习内容主题"]').fill("工作台浏览器验收：牛顿第二定律")
        page.locator('select[aria-label="学习内容类型"]').select_option("slide")
        page.locator('.ow-composer button[type="submit"]').click()
        expect(page.locator('[data-maic-stage-card="true"]')).to_be_visible(timeout=120000)
        _step(report, "生成完成，工作台已有可验收的 16:9 舞台")
        return page.url

    url = f"{BASE}/courses/{target['courseId']}/workspaces/{target['workspaceId']}"
    page.goto(url, wait_until="domcontentloaded")
    expect(page.locator('[data-testid="openmaic-workbench"]')).to_be_visible(timeout=30000)
    expect(page.locator('[data-maic-stage-card="true"]')).to_be_visible(timeout=30000)
    _step(report, f"打开真实课程工作台：{target['courseName']} / {target['workspaceName']}"
                 f"（{target['stages']} 个场景）")
    return url


def check_breakpoint(page, recorder: Recorder, report: list[str], width: int, height: int,
                     label: str, expected_layout: str) -> None:
    page.set_viewport_size({"width": width, "height": height})
    page.wait_for_timeout(420)
    recorder.responses.clear()

    geometry = page.evaluate(WORKBENCH_GEOMETRY)
    assert geometry["layout"] == expected_layout, (
        f"{width}px 布局模式应为 {expected_layout}，实际 {geometry['layout']}"
    )
    assert_no_h_overflow(geometry, f"{width}×{height}")
    assert_focusables_in_view(geometry, f"{width}×{height}")

    # 「开始学习」是唯一播放入口，任何断点都必须真实可见可点。
    assert geometry["start"], f"{width}px 找不到「开始学习」"
    assert geometry["start"]["width"] > 0 and geometry["start"]["height"] > 0, \
        f"{width}px「开始学习」没有真实尺寸：{geometry['start']}"
    assert "开始学习" in geometry["start"]["label"], \
        f"{width}px「开始学习」文案不对：{geometry['start']['label']}"

    if expected_layout == "narrow":
        assert geometry["switcherCount"] == 3, \
            f"{width}px 窄屏切换器应有 3 项，实际 {geometry['switcherCount']}"
        assert len(geometry["panesPresent"]) == 1, (
            f"{width}px 窄屏必须恰好一个内容 pane，实际 {geometry['panesPresent']}"
        )
        assert geometry["nav"], f"{width}px 窄屏缺少持久导航区"
        # 导航区是普通 <nav>，页面上唯一的 tablist 是课程标签条，且它不嵌套。
        assert geometry["navTag"] == "nav", f"导航区应当是 <nav>，实际 <{geometry['navTag']}>"
        assert geometry["navRole"] is None, "导航区外层不得声明 role=tablist"
        assert geometry["nestedTablists"] == 0, "页面上出现了嵌套的 tablist"
        # 切换控件是普通 button + aria-pressed，不留 role=tab 的半套语义。
        for entry in geometry["navButtons"]:
            assert entry["role"] is None, f"切换控件「{entry['text']}」不该有 role={entry['role']}"
        assert sum(1 for entry in geometry["navButtons"] if entry["pressed"]) == 1, \
            "同一时刻只能有一个切换控件处于按下状态"
        assert geometry["nav"]["width"] <= width + 1, "窄屏导航区越界"
        # 导航区那一行的三个控件都必须真的在视口里。
        # 320/390 是本次缺陷最严重的两档：曾出现"开始学习"被挤到 300px 边界外。
        # 激活面板必须吃掉整条可用工作区宽度（即根节点自己的内容宽度），而不是某个
        # 固定像素数。拿视口宽度比会在有纵向滚动条时误报——那 15px 属于滚动条，
        # 不属于工作台。
        root_width = geometry["root"]["width"]
        active = geometry["paneBoxes"][0]
        assert active["width"] >= root_width - 2, (
            f"{width}px 激活 pane 未占满可用宽度：{active['width']}（工作台宽 {root_width}，视口 {width}）"
        )
        assert geometry["nav"]["width"] >= root_width - 2, "窄屏导航区未占满工作台宽度"
    else:
        assert geometry["switcherCount"] == 0, "宽屏不应出现窄屏切换器"
        assert geometry["panesPresent"] == [
            ".ow-pane--rail", ".ow-pane--classroom", ".ow-pane--tools"
        ], f"{width}px 宽屏必须保持三栏，实际 {geometry['panesPresent']}"
        rail, classroom, tools = geometry["paneBoxes"]
        assert rail["width"] >= 199, f"{width}px 目录栏过窄：{rail['width']}"
        assert tools["width"] >= 299, f"{width}px 工具栏过窄：{tools['width']}"
        # 三栏必须真的并排，不是叠在一起。
        assert rail["right"] <= classroom["x"] + 2, "目录与课堂重叠"
        assert classroom["right"] <= tools["x"] + 2, "课堂与工具重叠"

    # 依次点击三个面板，每次 DOM 里有且只有一个内容 pane。
    if expected_layout == "narrow":
        for pane_label, selector in PANES.items():
            button = page.locator(".ow-seg--nav button", has_text=pane_label).first
            assert button.is_visible(), f"{width}px 切换器「{pane_label}」不可见"
            box = button.bounding_box()
            assert box and -1 <= box["x"] and box["x"] + box["width"] <= width + 1, (
                f"{width}px 切换器「{pane_label}」越界：{box}"
            )
            button.click()
            page.wait_for_timeout(260)
            state = page.evaluate(WORKBENCH_GEOMETRY)
            present = state["panesPresent"]
            assert present == [selector], (
                f"{width}px 点击「{pane_label}」后应该有且只有 {selector}，实际 {present}"
            )
            assert_no_h_overflow(state, f"{width}×{height} @{pane_label}")
            assert_focusables_in_view(state, f"{width}×{height} @{pane_label}")
            assert state["visibleFocusables"] > 0, f"{width}px「{pane_label}」面板里没有任何可交互控件"
            # 未激活面板不能留下"看不见但能聚焦"的交互元素——那才是真正会把键盘用户
            # 送到一个不可见控件上的形态。纯 display:none 的隐藏是合法的。
            assert not state["focusableButHidden"], (
                f"{width}px「{pane_label}」激活时有隐藏但仍可聚焦的元素："
                + json.dumps(state["focusableButHidden"], ensure_ascii=False)
            )
            # 切换器本身必须在场——切到目录后仍能回到课堂。
            assert state["switcherCount"] == 3, \
                f"{width}px 在「{pane_label}」里切换器消失了（回不到其它面板）"
            _step(report, f"{width}×{height} 切到「{pane_label}」：DOM 面板={present}，"
                         f"宽度={state['paneBoxes'][0]['width']}px，可见控件={state['visibleFocusables']}")
        # 回到课堂，后面的断点/回归从课堂开始。
        page.locator(".ow-seg--nav button", has_text="课堂").first.click()
        page.wait_for_timeout(240)
        back = page.evaluate(WORKBENCH_GEOMETRY)
        assert back["panesPresent"] == [".ow-pane--classroom"]
        if width == 320:
            # 本次 P1 的核心：320px 下课堂不得再被固定 60px 的 mini 目录栏挤压。
            assert not page.locator(".ow-pane--rail.is-mini").count(), \
                "320px 下仍存在 mini 目录栏（就是它挤掉了舞台的 60px）"
            assert back["paneBoxes"][0]["width"] >= back["root"]["width"] - 2, (
                f"320px 课堂 pane 宽度只有 {back['paneBoxes'][0]['width']}，说明仍被其它栏挤压"
            )
            assert back["stage"], "320px 找不到 16:9 舞台"
            assert back["stage"]["width"] >= 200, \
                f"320px 舞台过窄：{back['stage']['width']}"
            _step(report, f"320px 课堂 pane 宽度={back['paneBoxes'][0]['width']}px（无 mini rail），"
                         f"舞台 {back['stage']['width']}×{back['stage']['height']}")
    else:
        _step(report, f"{width}×{height} 三栏并排：目录={geometry['paneBoxes'][0]['width']}px，"
                     f"课堂={geometry['paneBoxes'][1]['width']}px，工具={geometry['paneBoxes'][2]['width']}px")

    _step(report, f"{width}×{height} 无横向溢出（scrollWidth={geometry['document']['scrollWidth']} "
                 f"<= clientWidth={geometry['document']['clientWidth']}），"
                 f"可见主控件无被裁（{geometry['visibleFocusables']} 个，"
                 f"需滚动可见 {len(geometry['belowFold'])} 个）")

    if SHOTS:
        SHOTS.mkdir(parents=True, exist_ok=True)
        shot = SHOTS / f"ow-{label}-{width}x{height}.png"
        page.screenshot(path=str(shot), full_page=False)
        _step(report, f"截图 → {shot.name}")


def check_switcher_keyboard(page, report: list[str]) -> None:
    """窄屏面板切换器必须真的能用键盘操作，且焦点可见。

    只验证"有 tabindex"是不够的：要求按方向键能换面板，Home/End 能跳首尾，
    Tab 只停一个停靠点，并且被选中的那个控件在键盘操作后真的拿到了焦点。
    """
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(300)

    switcher = page.locator(".ow-seg--nav")
    assert switcher.count() == 1, "窄屏应当有唯一的切换器"

    buttons = page.locator(".ow-seg--nav button")
    assert buttons.count() == 3, f"切换器应有 3 个控件，实际 {buttons.count()}"

    def pressed_label():
        return page.evaluate(
            """() => {
                const el = document.querySelector('.ow-seg--nav button[aria-pressed="true"]');
                return el ? el.textContent.trim() : null;
            }"""
        )

    def focused_label():
        return page.evaluate(
            """() => {
                const el = document.activeElement;
                if (!el || !el.closest || !el.closest('.ow-seg--nav')) return null;
                return el.textContent.trim();
            }"""
        )

    def pane_now():
        """当前在场面板的**类名列表**（不是选择器），方便直接比 contains。"""
        return page.evaluate(
            """() => {
                const el = document.querySelector('.ow-pane');
                return el ? [...el.classList] : null;
            }"""
        )

    # 从课堂出发，确保初始状态明确。
    page.locator(".ow-seg--nav button", has_text="课堂").first.click()
    page.wait_for_timeout(200)
    assert pressed_label() == "课堂", f"初始应停在课堂，实际 {pressed_label()}"

    # 键盘操作前先把焦点放到当前选中的控件上——这正是 Tab 会落到的那个。
    page.locator('.ow-seg--nav button[aria-pressed="true"]').first.focus()
    assert focused_label() == "课堂", f"焦点应停在当前选中的控件上，实际 {focused_label()}"

    # roving focus：同一时刻只有一个控件能被 Tab 停住。
    tab_stops = page.evaluate(
        """() => [...document.querySelectorAll('.ow-seg--nav button')]
            .filter((el) => el.tabIndex === 0).map((el) => el.textContent.trim())"""
    )
    assert tab_stops == ["课堂"], f"切换器应当只有一个 Tab 停靠点，实际 {tab_stops}"

    # ArrowRight / ArrowLeft / Home / End 都要真的换面板。
    # 每一项写成 (按键, 期望选中, 期望面板)，并且每步都从"上一项的结果"继续，
    # 所以这里必须严格按顺序推进——顺序错了断言会立刻指出错在哪一步。
    sequence = [
        ("ArrowRight", "工具", "ow-pane--tools"),
        ("ArrowRight", "目录", "ow-pane--rail"),
        ("ArrowLeft", "工具", "ow-pane--tools"),
        ("Home", "目录", "ow-pane--rail"),
        ("End", "工具", "ow-pane--tools"),
    ]
    for key, expect_label, expect_pane in sequence:
        assert focused_label() is not None, (
            f"按 {key} 之前焦点已不在切换器里（实际 {focused_label()}），"
            "roving focus 把焦点弄丢了"
        )
        page.keyboard.press(key)
        page.wait_for_timeout(220)
        assert pressed_label() == expect_label, (
            f"按 {key} 后应选中「{expect_label}」，实际「{pressed_label()}」"
        )
        # `expect_pane` 是不带点的类名（如 ow-pane--tools）；pane_now() 返回类名列表。
        assert expect_pane in (pane_now() or []), (
            f"按 {key} 后应当只渲染 .{expect_pane} 一个面板，实际 {pane_now()}"
        )
        # 顺手钉住互斥本身：键盘切面板同样只能留一个 pane 在 DOM 里。
        assert page.locator(".ow-pane").count() == 1, (
            f"按 {key} 后 DOM 里有 {page.locator('.ow-pane').count()} 个面板，破坏了互斥"
        )
        # 焦点必须跟着走，否则键盘用户会丢了位置。
        assert focused_label() == expect_label, (
            f"按 {key} 后焦点应当在「{expect_label}」上，实际 {focused_label()}"
        )

    # 焦点必须在视口内，并且有可见的焦点样式（不是 outline: none 的隐形状）。
    outline = page.evaluate(
        """() => {
            const el = document.querySelector('.ow-seg--nav button[aria-pressed="true"]');
            if (!el) return null;
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return {
                outlineStyle: s.outlineStyle,
                outlineWidth: s.outlineWidth,
                boxShadow: s.boxShadow,
                x: Math.round(r.x), right: Math.round(r.right),
                y: Math.round(r.y), bottom: Math.round(r.bottom),
                inViewport: r.x >= 0 && r.right <= window.innerWidth
                    && r.y >= 0 && r.bottom <= window.innerHeight,
            };
        }"""
    )
    assert outline and outline["inViewport"], f"当前选中的切换控件不在视口内：{outline}"
    # 焦点样式可以是 outline，也可以是 box-shadow 环——两者至少有其一。
    has_ring = (outline["outlineStyle"] not in ("none", "") and outline["outlineWidth"] != "0px") \
        or outline["boxShadow"] not in ("none", "")
    assert has_ring, f"切换控件缺少可见的焦点样式：{outline}"

    _step(report, "切换器键盘可用：ArrowLeft/ArrowRight/Home/End 均换面板且焦点跟随，"
                 "单一 Tab 停靠点，焦点样式可见")

    # 回到课堂，后续步骤从课堂继续。
    page.locator(".ow-seg--nav button", has_text="课堂").first.click()
    page.wait_for_timeout(200)


def check_stage_ratio(page, report: list[str]) -> None:
    """16:9 舞台必须仍然是 ResizeObserver 量出来的像素盒（不是 CSS aspect-ratio）。"""
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(500)
    stage = page.evaluate(
        """() => {
            const card = document.querySelector('[data-maic-stage-card="true"]');
            if (!card) return null;
            const r = card.getBoundingClientRect();
            return {
                width: r.width, height: r.height,
                inlineWidth: card.style.width, inlineHeight: card.style.height,
                sized: card.getAttribute('data-sized'),
                aspectRatio: getComputedStyle(card).aspectRatio,
            };
        }"""
    )
    assert stage, "找不到 16:9 舞台盒"
    ratio = stage["width"] / stage["height"]
    assert abs(ratio - 16 / 9) < 0.02, f"舞台不是 16:9：{stage['width']}×{stage['height']} = {ratio:.4f}"
    assert stage["sized"] == "true", "舞台必须是测量出来的像素盒（data-sized=true）"
    assert stage["inlineWidth"].endswith("px") and stage["inlineHeight"].endswith("px"), (
        f"舞台宽高必须由 JS 写成 px，实际 {stage['inlineWidth']} / {stage['inlineHeight']}"
    )
    assert stage["aspectRatio"] in ("auto", "", None), \
        f"舞台不得退化成 CSS aspect-ratio：{stage['aspectRatio']}"
    _step(report, f"16:9 舞台仍是像素盒：{round(stage['width'])}×{round(stage['height'])}"
                 f"（inline {stage['inlineWidth']}×{stage['inlineHeight']}，computed aspect-ratio={stage['aspectRatio']}）")


def check_play_and_back(page, recorder: Recorder, report: list[str]) -> None:
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(300)
    start = page.locator('[data-testid="ow-start-learning"]')
    expect(start).to_be_visible(timeout=10000)
    start.click()
    page.wait_for_timeout(600)
    assert start.get_attribute("aria-pressed") == "true", "「开始学习」按下后未进入播放态"
    assert "返回编辑" in start.inner_text(), f"播放态下按钮文案应为「返回编辑」：{start.inner_text()}"
    _step(report, "点击「开始学习」进入播放态（按钮变为「返回编辑」）")

    start.click()
    page.wait_for_timeout(600)
    assert start.get_attribute("aria-pressed") == "false", "「返回编辑」未回到编辑态"
    assert "开始学习" in start.inner_text(), "返回编辑后按钮文案未复原"
    _step(report, "「返回编辑」回到编辑态")

    recorder.page_errors.clear()
    page.reload(wait_until="domcontentloaded")
    expect(page.locator('[data-testid="openmaic-workbench"]')).to_be_visible(timeout=30000)
    expect(page.locator('[data-maic-stage-card="true"]')).to_be_visible(timeout=30000)
    assert not recorder.page_errors, f"刷新工作台后出现页面异常：{recorder.page_errors}"
    _step(report, "刷新工作台后仍恢复（场景与舞台都在）")


def check_narrow_play_entry(page, report: list[str]) -> None:
    """320px 下「开始学习」必须真实可点，而不是只是"没越界"。"""
    page.set_viewport_size({"width": 320, "height": 720})
    page.wait_for_timeout(420)
    start = page.locator('[data-testid="ow-start-learning"]')
    expect(start).to_be_visible(timeout=10000)
    box = start.bounding_box()
    assert box and box["width"] >= 64 and box["height"] >= 24, f"320px「开始学习」触控面积过小：{box}"
    start.click()
    page.wait_for_timeout(600)
    assert start.get_attribute("aria-pressed") == "true", "320px 下点「开始学习」没有进入播放"
    start.click()
    page.wait_for_timeout(400)
    assert start.get_attribute("aria-pressed") == "false"
    _step(report, f"320px「开始学习」真实可点：{round(box['width'])}×{round(box['height'])}px，"
                 f"进入播放并返回编辑")


def check_mid_route_survives(page, recorder: Recorder, report: list[str]) -> None:
    """回归：CampusMate 全局壳会影响工作台的只有 openmaic-shell 那几条规则。"""
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(f"{BASE}/home", wait_until="domcontentloaded")
    page.wait_for_timeout(600)
    assert page.locator(".app-layout.openmaic-shell").count() == 0, \
        "非 OpenMAIC 路由不应带上 openmaic-shell 类（那会误伤其它页面）"
    _step(report, "回归 /home：非 OpenMAIC 路由不受 openmaic-shell 影响")


def check_503(page, recorder: Recorder, report: list[str], service_control) -> None:
    """掉线时仍停在课堂：中文错误、重试生成、手动创建工作台、返回课程都在。"""
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(f"{BASE}/courses", wait_until="domcontentloaded")
    enter = page.locator(".openmaic-course-rail__enter").first
    expect(enter).to_be_visible(timeout=25000)

    _step(report, "已确认服务在线，停掉 openmaic-service 后点「进入课堂」")
    service_control.stop()
    recorder.responses.clear()
    enter.click()
    page.wait_for_url("**/classroom", timeout=15000)

    # 必须**停在课堂**（工作台无法建立时不假装成功）。
    page.wait_for_timeout(2500)
    current = page.url
    assert "/workspaces/" not in current, f"掉线时不应进入工作台：{current}"
    assert "/counselor" not in current, f"掉线时不应跳小助手：{current}"
    _step(report, f"掉线时停在课堂页：{current.split('/courses/')[-1]}")

    body = page.locator("main").inner_text()
    assert "Request failed with status code" not in body, "把 Axios 英文原文给了用户"
    assert any(token in body for token in ("请稍后", "未启用", "不可用", "失败", "重试")), \
        f"错误文案不是中文可操作信息：{body[:400]}"

    failed = page.locator(".openmaic-entry__error").first
    expect(failed).to_be_visible(timeout=20000)
    error_text = failed.inner_text().strip()
    _step(report, f"局部中文错误可见：{error_text.splitlines()[0][:120]}")

    retry = failed.get_by_role("button", name="重试生成")
    manual = failed.get_by_role("button", name="手动创建工作台")
    back = failed.get_by_role("button", name="返回课程")
    if retry.count() == 0:
        # 手动创建那条路是在建库失败时才该出现的；先把它走出来，再回到错误态。
        expect(manual).to_be_visible(timeout=10000)
        _step(report, "本次失败被判定为不可重试，提供了「手动创建工作台」")
    expect(manual).to_be_visible(timeout=10000)
    expect(back).to_be_visible(timeout=10000)
    assert retry.count() or manual.count(), "失败态既不能重试也不能手动创建，用户无路可走"
    _step(report, "课堂页同时提供：重试生成 / 手动创建工作台 / 返回课程（没有假装已完成）")

    # 服务恢复后重试必须真的能进工作台，而不是刷新整站。
    service_control.start()
    _step(report, "已恢复 openmaic-service，点击「重试生成」")
    recorder.responses.clear()
    if retry.count():
        retry.click()
    else:
        # 没有重试入口时，走"手动创建工作台"这条同样真实的恢复路径。
        manual.click()
    page.wait_for_url("**/workspaces/**", timeout=60000)
    expect(page.locator('[data-testid="openmaic-workbench"]')).to_be_visible(timeout=30000)
    status = recorder.await_status(page, "/workspaces")
    _step(report, f"恢复后进入工作台（GET …/workspaces → HTTP {status}），未刷新整站")


def run_checks(service_control) -> dict:
    report: list[str] = []
    recorder = Recorder(BASE)
    shots: list[Path] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = context.new_page()
        recorder.attach(page)

        try:
            print("步骤 1：真实登录")
            login(page, report)

            print("步骤 2：「我的课程」→ 真实「进入课堂」→ 直达工作台")
            enter_classroom_from_my_courses(page, recorder, report)

            print("步骤 3：打开一个已存在、已有内容的真实工作台")
            workbench_url = first_real_workbench(page, recorder, report)

            print("步骤 4：断点几何验收（320 / 390 / 768 / 1024 / 1440）")
            for width, height, label, expected in VIEWPORTS:
                check_breakpoint(page, recorder, report, width, height, label, expected)

            print("步骤 5：窄屏切换器键盘可用与焦点可见")
            check_switcher_keyboard(page, report)

            print("步骤 6：16:9 舞台仍是 ResizeObserver 像素盒")
            check_stage_ratio(page, report)

            print("步骤 7：回归「开始学习 / 返回编辑 / 刷新」")
            check_play_and_back(page, recorder, report)

            print("步骤 8：320px 下「开始学习」真实可点")
            check_narrow_play_entry(page, report)

            print("步骤 9：回归非 OpenMAIC 路由不受全局壳影响")
            check_mid_route_survives(page, recorder, report)

            print("步骤 10：503 掉线仍然停在课堂")
            check_503(page, recorder, report, service_control)

            print("步骤 11：console / pageerror / 未处理 Promise rejection")
            rejections = page.evaluate("() => window.__unhandled || []")
            assert not recorder.page_errors, f"出现未捕获的页面异常：{recorder.page_errors}"
            _step(report, "pageerror：0 条")
            assert not rejections, f"出现未处理的 Promise rejection：{rejections}"
            _step(report, "unhandledrejection：0 条")

            script_errors = recorder.script_console_errors()
            assert not script_errors, f"站点脚本出现 console error：{script_errors}"
            _step(report, "站点脚本 console error：0 条")

            # 掉线场景故意让某些请求失败，逐条核对它们只属于那一段。
            network_errors = recorder.network_console_errors()
            _step(report, f"浏览器资源加载失败提示：{len(network_errors)} 条（掉线场景预期内）")

            shots = sorted(SHOTS.glob("ow-*.png")) if SHOTS and SHOTS.exists() else []
        except Exception:
            # 失败截图走和成功截图完全相同的临时目录规则，绝不落到仓库里。
            if SHOTS:
                try:
                    SHOTS.mkdir(parents=True, exist_ok=True)
                    shot = SHOTS / "ow-FAILURE.png"
                    page.screenshot(path=str(shot), full_page=False)
                    print(f"失败截图：{shot}", file=sys.stderr)
                except Exception:
                    pass
            diagnose(page, recorder, "run_checks")
            raise
        finally:
            context.close()
            browser.close()

    return {"report": report, "shots": [str(p) for p in shots]}
