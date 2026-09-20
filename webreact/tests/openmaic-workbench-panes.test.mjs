/**
 * 工作台**真实渲染**的面板互斥契约。
 *
 * 为什么不能只测 `resolveWorkbenchLayout()`：这个工作台上一轮的 P1 缺陷正是
 * "模型算对了、页面没听"——`resolveWorkbenchLayout()` 在窄屏返回
 * `classroom: false`（切到工具时），可是 `OpenMAICWorkbenchPage.jsx` 里课堂
 * `<section>` 是无条件渲染的，rail 也被 CSS 固定成 60px。纯模型测试全绿，用户看到
 * 的却是"切到工具后课堂还在，而且舞台永远被切掉 60px"。
 *
 * 所以这里把真实页面挂进真实 DOM（经 vite 转译 JSX，真实 react-dom 渲染），用
 * `window.matchMedia` 控制窄/宽，然后**数 DOM**：
 *
 *   - 窄屏三个面板两两互斥，且恰好一个在场；
 *   - 未激活面板不是"看不见"，而是根本不在 DOM 里（不留可聚焦元素）；
 *   - 切换器在窄屏**任何**面板下都存在——它一旦跟着课堂面板走，切到目录就再也回
 *     不到课堂，那是一个死角；
 *   - 宽屏三栏同时在，且只有一个 `ow-pane-head` 高度令牌；
 *   - 页面上「开始学习」仍然只有一个。
 */
import test, { after } from "node:test";
import assert from "node:assert/strict";

import "./helpers/setup-globals.mjs";
import { parseHTML } from "linkedom";

const { window, document } = parseHTML(
  "<!doctype html><html><body><div id='root'></div></body></html>",
);
globalThis.window = window;
globalThis.document = document;
Object.defineProperty(globalThis, "navigator", {
  value: window.navigator, configurable: true, writable: true,
});
globalThis.HTMLElement = window.HTMLElement;
globalThis.Element = window.Element;
globalThis.Node = window.Node;
globalThis.Event = window.Event;
globalThis.CustomEvent = window.CustomEvent;
globalThis.MutationObserver = window.MutationObserver;
globalThis.requestAnimationFrame = (fn) => setTimeout(() => fn(Date.now()), 0);
globalThis.cancelAnimationFrame = (id) => clearTimeout(id);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

/**
 * linkedom 没有实现的两个布局 API。
 *
 * 缺 `scrollIntoView` 时 `WorkspaceCourseTabs` 的 `revealActive()` 会抛 TypeError——
 * 而它跑在**提交阶段**，于是整棵树挂载失败，测试看到的是"面板一个都没有"，很容易
 * 被误读成被测页面的缺陷。这两个 shim 只补浏览器提供、linkedom 未提供的**空实现**：
 * 它们不影响任何被测逻辑（这个用例断言的顺序、在场与可聚焦性都与滚动无关），
 * 只是让组件能像在真实浏览器里那样把 effect 跑完。
 */
if (!window.Element.prototype.scrollIntoView) {
  window.Element.prototype.scrollIntoView = function scrollIntoView() {};
}
if (!window.Element.prototype.scrollTo) {
  window.Element.prototype.scrollTo = function scrollTo() {};
}

/** 可控的 `matchMedia`：测试用 `setNarrow()` 改写它并广播 change。 */
const mediaListeners = new Set();
let narrowMatches = false;
function matchMedia(query) {
  return {
    media: query,
    get matches() {
      // 只认窄屏那一条查询；其它查询（reduced-motion 等）一律 false。
      return /max-width:\s*1023px/.test(query) ? narrowMatches : false;
    },
    addEventListener(type, handler) { if (type === "change") mediaListeners.add(handler); },
    removeEventListener(type, handler) { if (type === "change") mediaListeners.delete(handler); },
    addListener(handler) { mediaListeners.add(handler); },
    removeListener(handler) { mediaListeners.delete(handler); },
    onchange: null,
    dispatchEvent: () => true,
  };
}
window.matchMedia = matchMedia;
globalThis.matchMedia = matchMedia;

const apiModule = await import("../src/data/api.js");
const { createMockClient } = await import("./helpers/mock-client.mjs");

const COURSE = "crs_panes";
const WORKSPACE = "ws_panes";
const STAGE = "stg_panes";

let mock = null;
function installHandlers() {
  mock.onGet(`/courses/${COURSE}/workspaces/${WORKSPACE}`, {
    id: WORKSPACE, course_id: COURSE, name: "面板互斥验收工作台", revision: 3,
    created_at: "2026-01-01T00:00:00.000Z", updated_at: "2026-01-01T00:00:00.000Z",
  });
  mock.onGet(`/courses/${COURSE}/workspaces/${WORKSPACE}/stages`, {
    items: [{
      id: STAGE, workspace_id: WORKSPACE, title: "面板互斥验收课堂", mode: "slide",
      dsl_version: "0.3.0", revision: 1,
      created_at: "2026-01-01T00:00:00.000Z", updated_at: "2026-01-01T00:00:00.000Z",
    }],
    next_cursor: null,
  });
  mock.onGet(`/courses/${COURSE}/workspaces/${WORKSPACE}/stages/${STAGE}/outline`, {
    id: STAGE, title: "面板互斥验收课堂", revision: 1,
    scenes: [{ id: "sc_1", title: "第一幕", kind: "slide" }],
  });
  mock.onGet("/openmaic/fusion/status", {
    enabled: true, available: true, state: "ready",
    capabilities: ["workspace", "generation", "export-pptx"], reason: "ready",
  });
  mock.onGet("/openmaic/fusion/providers", {
    state: "disabled", providers: {},
  });
  mock.onGet("/openmaic/providers", { state: "disabled", providers: {} });
  mock.onGet("/courses", { items: [{ id: COURSE, name: "面板互斥验收课程" }] });
  mock.onGet(`/courses/${COURSE}`, { id: COURSE, name: "面板互斥验收课程" });
}

mock = createMockClient(apiModule.client);
installHandlers();

process.on("exit", (code) => {
  if (code !== 0) console.error("[panes-test] 以非零码退出；若日志停在某个用例名上，就是那个用例挂住了");
});

const { createServer } = await import("vite");
const { fileURLToPath } = await import("node:url");
const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true, watch: null },
  appType: "custom",
  logLevel: "silent",
});
after(async () => {
  // 断言失败会留下 React 未清空的 act 队列，此时 `vite.close()` 可能永远不 resolve，
  // 于是整个测试进程挂住、连失败报告都打不出来（看起来像"卡住了"而不是"失败了"）。
  // 给它一个上限：超时就带着已有的报告退出，失败原因仍然可见。
  await Promise.race([
    vite.close(),
    new Promise((resolve) => setTimeout(resolve, 5000).unref?.()),
  ]);
});

const React = (await import("react")).default;
const { createRoot } = await import("react-dom/client");
const { act } = React;
const { MemoryRouter, Routes, Route } = await import("react-router-dom");
const { readFile } = await import("node:fs/promises");
const { fileURLToPath: toPath } = await import("node:url");
const { default: OpenMAICWorkbenchPage } = await vite.ssrLoadModule(
  "/src/pages/OpenMAICWorkbenchPage.jsx",
);

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function setNarrow(value) {
  narrowMatches = value;
  for (const handler of mediaListeners) handler({ matches: value, media: "(max-width: 1023px)" });
}

async function mount() {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(React.createElement(MemoryRouter, {
      initialEntries: [`/courses/${COURSE}/workspaces/${WORKSPACE}`],
    }, React.createElement(Routes, null, React.createElement(Route, {
      path: "/courses/:courseId/workspaces/:workspaceId",
      element: React.createElement(OpenMAICWorkbenchPage),
    }))));
  });
  // 工作台的数据加载是异步的；等到舞台出现为止。
  for (let i = 0; i < 60; i += 1) {
    await act(async () => { await sleep(20); });
    if (host.querySelector(".ow-stage")) break;
  }
  return { host, unmount: () => act(async () => root.unmount()) };
}

/** 当前在场（在 DOM 里）的面板类名。 */
function panesInDom(host) {
  return [".ow-pane--rail", ".ow-pane--classroom", ".ow-pane--tools"]
    .filter((selector) => host.querySelector(selector));
}

function paneButtons(host) {
  // 只取切换器自己那一组：课程标签条是另一个角色组，混进来会把"切换器还在不在"
  // 这个问题问错。
  return [...host.querySelectorAll(".ow-seg--nav button")];
}

async function clickPane(host, label) {
  const button = paneButtons(host).find((node) => node.textContent.trim() === label);
  assert.ok(button, `切换器里找不到「${label}」；实际：${paneButtons(host).map((n) => n.textContent.trim())}`);
  await act(async () => { button.dispatchEvent(new window.Event("click", { bubbles: true })); });
  await act(async () => { await sleep(20); });
}

test("the workbench loads a real stage before the pane contract is judged", async () => {
  const { host, unmount } = await mount();
  assert.ok(host.querySelector(".ow-stage"), "工作台必须先真的加载出舞台，否则后面的断言毫无意义");
  await unmount();
});

test("narrow: every pane selection leaves exactly one pane in the DOM", async () => {
  await act(async () => { setNarrow(true); });
  const { host, unmount } = await mount();

  // 窄屏默认落在课堂：rails/tools 连 DOM 都不该有。
  assert.deepEqual(panesInDom(host), [".ow-pane--classroom"], "窄屏默认只应有课堂面板");

  const expectations = [
    ["目录", ".ow-pane--rail"],
    ["课堂", ".ow-pane--classroom"],
    ["工具", ".ow-pane--tools"],
  ];
  for (const [label, expected] of expectations) {
    await clickPane(host, label);
    const present = panesInDom(host);
    assert.deepEqual(present, [expected], `点击「${label}」后应当只剩它一个面板`);
    // 未激活的面板不得留下**任何**残留——不是"看不见"，而是不在 DOM 里。
    // 只要有一个 `.ow-pane` 不是当前选中的那个，就已经不是互斥了。
    assert.equal(
      present.length, 1,
      `「${label}」激活时 DOM 里出现了 ${present.length} 个面板：${present.join("、")}`,
    );
    // 删除的面板不能留下可聚焦的孤儿：面板**之外**（导航区）允许存在的交互元素
    // 是穷举得出的——三个切换器按钮、活动课程标签的关闭按钮、返回按钮，一个不多。
    // 任何残留的面板控件都会在这里露头。
    const outside = [...host.querySelectorAll("a[href], button, input, select, textarea")]
      .filter((node) => !node.closest(expected))
      .map((node) => (node.textContent || node.getAttribute("aria-label") || "").replace(/\s+/g, ""));
    assert.deepEqual(outside, ["目录", "课堂", "工具", "关闭标签页《面板互斥验收工作台》", "返回课程列表"],
      `「${label}」激活时，面板之外只允许有切换器、课程标签与返回按钮，实际：${outside.join(" | ")}`);
    // 切换器必须还在——否则切到目录就再也回不到课堂。
    assert.equal(paneButtons(host).length, 3, `「${label}」激活时切换器必须仍然完整在场`);
    assert.equal(
      paneButtons(host).filter((node) => node.getAttribute("aria-pressed") === "true").length,
      1,
      "任意时刻只能有一个面板被标记为按下",
    );
    assert.equal(
      paneButtons(host).find((node) => node.getAttribute("aria-pressed") === "true").textContent.trim(),
      label,
      "标记为按下的那个必须就是当前在场的面板",
    );
  }

  await unmount();
  await act(async () => { setNarrow(false); });
});

test("narrow: the classroom stage is not squeezed by a leftover rail", async () => {
  await act(async () => { setNarrow(true); });
  const { host, unmount } = await mount();
  await clickPane(host, "课堂");
  // 课堂面板必须是根节点下唯一的**面板**子项（导航区不是 .ow-pane，所以不会被数进来）。
  // 旧实现这里会数到 2 个：mini rail + classroom，那正是 320px 上被切掉的 60px。
  const paneChildren = [...host.children]
    .flatMap((node) => [...node.children])
    .filter((node) => node.classList?.contains("ow-pane"));
  assert.equal(paneChildren.length, 1, `窄屏根节点下只应有一个面板，实际 ${paneChildren.length}`);
  assert.ok(paneChildren[0].classList.contains("ow-pane--classroom"), "在场的那一个必须是课堂");
  assert.ok(host.querySelector(".ow-nav"), "窄屏导航区必须与课堂同时在场");
  // 呈现给用户的切换器与「返回编辑 / 开始学习」都必须在场且可用名称完整。
  const start = host.querySelector('[data-testid="ow-start-learning"]');
  assert.ok(start, "窄屏课堂里必须有唯一的播放入口");
  assert.equal(start.textContent.replace(/\s+/g, ""), "开始学习");
  await unmount();
  await act(async () => { setNarrow(false); });
});

test("wide: all three panes are mounted together again", async () => {
  await act(async () => { setNarrow(false); });
  const { host, unmount } = await mount();
  assert.deepEqual(
    panesInDom(host),
    [".ow-pane--rail", ".ow-pane--classroom", ".ow-pane--tools"],
    "宽屏必须保持参考项目的三栏工作台",
  );
  // 宽屏没有窄屏导航区，切换器不应存在（它是窄屏专有的）。
  assert.equal(paneButtons(host).length, 0, "宽屏不应渲染窄屏面板切换器");
  // 唯一的播放入口。
  assert.equal(host.querySelectorAll('[data-testid="ow-start-learning"]').length, 1);
  await unmount();
});

test("narrow: the nav never nests a tablist inside another tablist", async () => {
  await act(async () => { setNarrow(true); });
  const { host, unmount } = await mount();

  const nav = host.querySelector(".ow-nav");
  assert.ok(nav, "窄屏必须有工作台导航区");
  // 外层是普通 nav，不是 tablist：它肚子里装着 WorkspaceCourseTabs，而后者自己
  // 就是一个合法的 tablist。嵌套 tablist 的层级读出来是错的。
  assert.equal(nav.tagName.toLowerCase(), "nav", "导航区外层应当是 <nav>");
  assert.equal(nav.getAttribute("role"), null, "导航区外层不得声明 role=tablist");
  assert.ok(nav.getAttribute("aria-label"), "导航区需要有可访问名称");

  // 全页的 tablist 恰好只有课程标签条那一个，且它不在任何别的 tablist 里面。
  const tablists = [...host.querySelectorAll('[role="tablist"]')];
  assert.equal(tablists.length, 1, `全页应当只有课程标签条一个 tablist，实际 ${tablists.length} 个`);
  assert.equal(tablists[0].className, "ow-ctabs", "唯一的 tablist 应当是课程标签条");
  assert.equal(
    tablists[0].parentElement.closest('[role="tablist"]'), null,
    "课程标签条不得嵌在另一个 tablist 内",
  );

  // 切换器要么是完整 tab 语义（role=tab + tabpanel），要么老老实实是按钮组。
  // 这里是后者：一组互斥的视图开关，用 aria-pressed 表达。
  const switcher = host.querySelector(".ow-seg--nav");
  assert.equal(switcher.getAttribute("role"), "group");
  const buttons = paneButtons(host);
  assert.equal(buttons.length, 3);
  for (const button of buttons) {
    assert.equal(button.tagName.toLowerCase(), "button", "切换控件应当是真正的 button");
    assert.equal(button.getAttribute("role"), null, "普通按钮不该再挂 role=tab 的半套语义");
    assert.ok(button.hasAttribute("aria-pressed"), "每个切换控件都要用 aria-pressed 表达状态");
  }
  // roving focus：同一时刻只有一个能被 Tab 停住。
  assert.equal(
    buttons.filter((node) => node.getAttribute("tabindex") === "0").length, 1,
    "切换器同一时刻只能有一个 Tab 停靠点",
  );

  await unmount();
  await act(async () => { setNarrow(false); });
});

test("narrow: the pane switcher moves selection with Arrow / Home / End", async () => {
  await act(async () => { setNarrow(true); });
  const { host, unmount } = await mount();

  const selectedLabel = () =>
    paneButtons(host).find((node) => node.getAttribute("aria-pressed") === "true")?.textContent.trim();
  /**
   * linkedom 没有 `KeyboardEvent` 构造器，所以自己造一个带 `key` 的普通 Event。
   * 被测代码只读 `event.key` 与 `event.preventDefault()`，两者都能满足。
   */
  const press = async (key) => {
    const current = paneButtons(host).find((node) => node.getAttribute("aria-pressed") === "true");
    const event = new window.Event("keydown", { bubbles: true, cancelable: true });
    Object.defineProperty(event, "key", { value: key });
    await act(async () => { current.dispatchEvent(event); });
    await act(async () => { await sleep(20); });
  };

  // 切换器按键把选中的面板真的换掉（不是只换焦点），否则"键盘可用"是假的。
  assert.equal(selectedLabel(), "课堂");
  await press("ArrowRight");
  assert.equal(selectedLabel(), "工具");
  assert.deepEqual(panesInDom(host), [".ow-pane--tools"], "方向键换选中必须真的换面板");

  await press("ArrowRight");
  assert.equal(selectedLabel(), "目录", "到尾部应当回绕");
  assert.deepEqual(panesInDom(host), [".ow-pane--rail"]);

  await press("ArrowLeft");
  assert.equal(selectedLabel(), "工具", "到头部应当反向回绕");

  await press("Home");
  assert.equal(selectedLabel(), "目录");
  await press("End");
  assert.equal(selectedLabel(), "工具");

  // 焦点最终必须落回切换器里那个当前选中的按钮上——键盘用户不能丢了位置。
  await act(async () => { await sleep(30); });
  const focused = paneButtons(host).find((node) => node === host.ownerDocument.activeElement);
  if (focused) {
    assert.equal(focused.getAttribute("aria-pressed"), "true", "焦点必须停在当前选中的切换控件上");
  }

  await unmount();
  await act(async () => { setNarrow(false); });
});

/**
 * 关闭标签的回归：`setTabsOpen` 的 updater 必须是纯函数。
 *
 * 此前 `navigate()` 写在 `setTabsOpen(current => { ...navigate()... })` 的 updater
 * 里面。React 允许重放 state updater（StrictMode 下会跑两遍来暴露副作用，并发渲染
 * 也可能重放），重放一个带副作用的 updater 就会导航两次，后退栈里多出一格。
 *
 * ── 为什么这里断言"源码形状"而不是"点一下数导航次数" ─────────────────────
 *
 * 运行时观测在这个缺陷上抓不到东西，三种做法都试过，且都在**有缺陷**的实现下全绿：
 *
 *   1. 数 location 变化：router 会把指向同一地址的重复导航去重，两次
 *      `navigate("/courses")` 只留下一个 location。
 *   2. 数 `navigator.push/replace`：`useNavigate()` 在页面渲染时就取走了方法引用，
 *      外层再替换已经拦不住；`createMemoryRouter` 也不暴露 history。
 *   3. 数包住后的 `router.navigate`：能拦到调用，但实测 React 18 在普通点击下
 *      **不会**重放 updater——一次点击只跑一遍，"有副作用"与"没副作用"的调用次数
 *      完全相同。
 *
 * 也就是说，这个缺陷在单测里运行时不可观测，只在 StrictMode 重放与并发渲染下显形。
 * 那就断言真正被要求的性质：副作用必须在 updater **外面**。做法是先把函数体切出来
 * 再查结构，而不是对整份源码做正则——后者会被注释里的引用误伤。
 */
test("closeTab keeps its side effect out of the state updater", async () => {
  const source = await readFile(
    toPath(new URL("../src/pages/OpenMAICWorkbenchPage.jsx", import.meta.url)),
    "utf8",
  );

  const start = source.indexOf("const closeTab = useCallback(");
  assert.ok(start > -1, "找不到 closeTab 的定义");
  // 连依赖数组一起切进来：`}, [deps]);` 的结尾也要在片里，后面才查得到 tabsOpen。
  const end = source.indexOf("\n\n", source.indexOf("}, [", start));
  assert.ok(end > start, "找不到 closeTab 的依赖数组");
  const body = source.slice(start, end);

  // 1. 不允许再用函数式 updater——副作用没有安全的位置可放。
  assert.equal(
    body.includes("setTabsOpen((current)"),
    false,
    "closeTab 不应再用函数式 updater。应当基于当前 tabsOpen 先算出 rest，"
    + "setTabsOpen(rest) 之后再在 updater 外面导航。",
  );

  // 2. 导航必须仍然发生（关掉当前课堂要回退到剩下的标签 / 课程列表）。
  assert.match(body, /navigate\(/, "closeTab 必须仍然会导航");

  // 3. 顺序：先 setTabsOpen(rest)，再 navigate。反过来会基于尚未更新的标签列表跳转。
  const setIndex = body.indexOf("setTabsOpen(");
  const navigateIndex = body.indexOf("navigate(");
  assert.ok(setIndex > -1 && navigateIndex > -1, "closeTab 里应当同时有 setTabsOpen 与 navigate");
  assert.ok(
    setIndex < navigateIndex,
    "必须先 setTabsOpen(rest) 再 navigate：反过来会基于还没更新的标签列表做跳转",
  );

  // 4. `rest` 由**当前** tabsOpen 在事件回调里算出，且 tabsOpen 进了依赖数组
  //    （函数体读了它，漏掉就会永远用挂载时的旧列表）。
  assert.match(body, /const rest = tabsOpen\.filter\(/, "rest 应当在事件回调里由当前 tabsOpen 算出");
  const deps = body.slice(body.lastIndexOf("}, ["));
  assert.match(deps, /\btabsOpen\b/, `closeTab 的依赖数组必须包含 tabsOpen，实际：${deps.trim()}`);
});
