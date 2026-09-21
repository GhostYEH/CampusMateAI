/**
 * 真实渲染入口组件，并在 React.StrictMode 下断言它不会永久卡死。
 *
 * 这一条测试的存在理由，是此前只测"纯函数 + 源码字符串"漏掉了一个**真实阻断级**
 * 缺陷：入口页同时用了
 *   1) `started.current` 布尔量挡住第二次 effect；
 *   2) `[courseId]` 清理函数里 `epoch.current += 1`。
 * StrictMode 的"挂载 → 模拟卸载 → 再挂载"先让第一次 enter() 在 await 之后因代次
 * 不匹配而静默返回，第二次又因为布尔量不重跑，于是页面永久停在等待态。字符串断言
 * 与纯函数测试都看不见这种异步生命周期错误，只有把它真的挂进 StrictMode 才行。
 *
 * 所以这里用真实的 react-dom/client 挂载真实组件（经 vite ssrLoadModule 转译 JSX），
 * 配一个最小 DOM，并断言：
 *   - 最终不再停留在"正在确认受管服务状态…"；
 *   - 完整走完 context → fusion → workspace → stage → generation 链路；
 *   - StrictMode 的两次挂载只产生一次链路请求、一次工作台创建。
 */
import test, { after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import "./helpers/setup-globals.mjs";
import { parseHTML } from "linkedom";

// ── 最小 DOM：必须在 react-dom/client 之前装好 ──
const { window, document } = parseHTML(
  "<!doctype html><html><body><div id='root'></div></body></html>",
);
globalThis.window = window;
globalThis.document = document;
// Node 24 的 `navigator` 只有 getter，直接赋值会抛 TypeError。
Object.defineProperty(globalThis, "navigator", {
  value: window.navigator,
  configurable: true,
  writable: true,
});
globalThis.HTMLElement = window.HTMLElement;
globalThis.Element = window.Element;
globalThis.Node = window.Node;
globalThis.Event = window.Event;
globalThis.CustomEvent = window.CustomEvent;
globalThis.MutationObserver = window.MutationObserver;
globalThis.requestAnimationFrame = (fn) => setTimeout(() => fn(Date.now()), 0);
globalThis.cancelAnimationFrame = (id) => clearTimeout(id);
// 让 React 认为处在 act() 环境，否则 StrictMode 的"挂载→模拟卸载→再挂载"不会
// 按真实时序发生，测试就失去了意义（会漏掉这次要抓的回归）。
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!window.matchMedia) {
  window.matchMedia = () => ({
    matches: false,
    addEventListener() {},
    removeEventListener() {},
    addListener() {},
    removeListener() {},
  });
}
globalThis.matchMedia = window.matchMedia;

// ── 在 axios adapter 层拦截，不改动被测模块 ──
// ES module 的导出是只读的，无法替换 api.js 的函数；拦截 adapter 反而更忠实：
// 真实 api.js 的路径拼接、请求头与幂等键都会真的被执行到。
// axios 在 import 时就创建了 client，所以必须先 import api.js 再装 adapter。
const apiModule = await import("../src/data/api.js");
const { createMockClient } = await import("./helpers/mock-client.mjs");
const mock = createMockClient(apiModule.client);

/**
 * 重新登记全部受控响应。
 *
 * 注意：`mock.reset()` 会连 handler 一起清掉，所以每次 reset 之后必须重新登记；
 * 只清请求记录的话，第二次进入工作台时会因为查不到 handler 而收到 404，表现为
 * "工作台只应创建一次；实际 0 次"这种误导性失败。
 */
function installHandlers() {
  mock.onGet("/courses", {
    items: [
      { id: "crs_x", name: "计算机科学概论", code: "CS101", semester: "2026秋" },
      { id: "crs_a", name: "课程A", code: "A101", semester: "2026秋" },
      { id: "crs_b", name: "课程B", code: "B101", semester: "2026秋" },
    ],
  });
  mock.onGet("/courses/crs_x/magicclass-context", {
    course_id: "crs_x",
    name: "计算机科学概论",
    code: "CS101",
    semester: "2026秋",
    description: "面向大一的计算学科导论。",
    knowledge_points: [{ name: "图灵机" }],
    chapters: ["计算的历史与未来", "算法"],
    materials: [{ id: "m1", title: "第一讲讲义", kind: "pdf" }],
    warnings: [],
    synced: true,
  });
  mock.onGet("/magicclass/fusion/status", {
    enabled: true, available: true, state: "ready",
    capabilities: ["workspace", "generation"], reason: "ready",
  });
  mock.onGet("/courses/crs_x/workspaces", { items: [], next_cursor: null });
  mock.onGet("/courses/crs_x/workspaces/ws_1/stages", { items: [], next_cursor: null });
  mock.onPost("/courses/crs_x/workspaces", {
    id: "ws_1", course_id: "crs_x", name: "计算机科学概论 · 学习课堂", revision: 1,
    created_at: "2026-01-01T00:00:00.000Z", updated_at: "2026-01-01T00:00:00.000Z",
  });
  mock.onPost("/courses/crs_x/workspaces/ws_1/generate", {
    job: { id: "job_1", status: "completed", step: "completed" }, stage_id: "st_1",
  });

  // 课程 B：用于 A→B 切换竞态测试（A 的 context 由用例单独挂起）。
  mock.onGet("/courses/crs_b/magicclass-context", {
    course_id: "crs_b", name: "课程B", code: "B101", semester: "2026秋",
    description: "课程 B 的真实简介。",
    knowledge_points: [], chapters: ["B章"], materials: [], warnings: [], synced: true,
  });
  mock.onGet("/magicclass/fusion/status", {
    enabled: true, available: true, state: "ready",
    capabilities: ["workspace", "generation"], reason: "ready",
  });
  mock.onGet("/courses/crs_b/workspaces", { items: [], next_cursor: null });
  mock.onGet("/courses/crs_b/workspaces/ws_b1/stages", { items: [], next_cursor: null });
  mock.onPost("/courses/crs_b/workspaces", {
    id: "ws_b1", course_id: "crs_b", name: "课程B · 学习课堂", revision: 1,
    created_at: "2026-01-01T00:00:00.000Z", updated_at: "2026-01-01T00:00:00.000Z",
  });
  mock.onPost("/courses/crs_b/workspaces/ws_b1/generate", {
    job: { id: "job_b1", status: "completed", step: "completed" }, stage_id: "st_b1",
  });
  // 课程 A 的工作台（A 一旦继续推进就会命中这些写接口，用于断言"不应发生"）。
  mock.onGet("/courses/crs_a/workspaces", { items: [], next_cursor: null });
  mock.onPost("/courses/crs_a/workspaces", {
    id: "ws_a1", course_id: "crs_a", name: "课程A · 学习课堂", revision: 1,
    created_at: "2026-01-01T00:00:00.000Z", updated_at: "2026-01-01T00:00:00.000Z",
  });
  mock.onGet("/courses/crs_a/workspaces/ws_a1/stages", { items: [], next_cursor: null });
  mock.onPost("/courses/crs_a/workspaces/ws_a1/generate", {
    job: { id: "job_a1", status: "completed", step: "completed" }, stage_id: "st_a1",
  });
}

installHandlers();

const calls = mock.requests;

/**
 * 一个可手动放行的响应。
 *
 * 用它把"A 的响应还在途中"变成可观察、可控制的状态：这正是用户复现切换课程时为
 * 什么 10 秒内没有任何 B 的请求——A 的在途请求一直没回来。
 */
function deferred() {
  let resolve;
  const promise = new Promise((r) => { resolve = r; });
  return { promise, resolve };
}

const { createServer } = await import("vite");
const { fileURLToPath } = await import("node:url");
const vite = await createServer({
  // 必须用 fileURLToPath：Windows 上 URL.pathname 会给出 "/D:/..." 这种带前导
  // 斜杠的路径，vite 解析入口时会失败。
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true, watch: null },
  appType: "custom",
  logLevel: "silent",
});

after(async () => { await vite.close(); });

const React = (await import("react")).default;
const { createRoot } = await import("react-dom/client");
const { StrictMode, act } = React;
const { MemoryRouter, Routes, Route, useNavigate } = await import("react-router-dom");

const { default: MagicClassClassroomEntryPage } = await vite.ssrLoadModule(
  "/src/pages/magicclassClassroomEntryPage.jsx",
);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function WorkbenchProbe() {
  return React.createElement("div", { "data-testid": "magicclass-workbench" }, "workbench");
}

/**
 * 挂载入口页，带一个可编程的路由跳转器。
 *
 * 路由同时声明工作台目标：入口页成功后会 `navigate` 到
 * `/courses/:courseId/workspaces/:workspaceId`，若没有对应 route，React Router 会
 * 打出 "No routes matched location" 警告，测试输出会被噪声填满，也可能掩盖真实问题。
 */
async function mount(initial = "/courses/crs_x/classroom") {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  let navigate = null;
  function Probe() {
    navigate = useNavigate();
    return null;
  }
  const routes = React.createElement(
    Routes,
    null,
    React.createElement(Route, { path: "/courses/:courseId/classroom", element: React.createElement(MagicClassClassroomEntryPage) }),
    React.createElement(Route, { path: "/courses/:courseId/workspaces/:workspaceId", element: React.createElement(WorkbenchProbe) }),
    React.createElement(Route, { path: "*", element: React.createElement("div", null, "not-found") }),
  );
  await act(async () => {
    root.render(
      React.createElement(StrictMode, null,
        React.createElement(MemoryRouter, { initialEntries: [initial] },
          React.createElement(React.Fragment, null,
            React.createElement(Probe),
            routes))),
    );
  });
  return {
    host,
    /** 在不卸载组件的前提下切换路由（真实课程切换就是这样发生的）。 */
    go: (to) => act(async () => { navigate(to); }),
    unmount: () => act(async () => root.unmount()),
  };
}

test("the entry page leaves the waiting state under StrictMode and runs the full chain", async () => {
  mock.reset();
  installHandlers();
  const { host, unmount } = await mount();

  // 给 StrictMode 的两次挂载与后续异步链路足够时间。
  for (let i = 0; i < 40; i += 1) await act(async () => { await sleep(25); });

  const text = host.textContent || "";
  assert.ok(
    !text.includes("正在确认受管服务状态"),
    `入口页不得永久停在等待态；实际内容：${text.slice(0, 300)}`,
  );

  const joined = calls.map((r) => `${r.method} ${r.url}`).join(" | ");
  for (const step of ["magicclass-context", "fusion/status", "/workspaces", "/stages", "/generate"]) {
    assert.ok(joined.includes(step), `缺少链路步骤 ${step}；实际：${joined}`);
  }

  // StrictMode 的第二次挂载必须复用在飞的那次，不得把整条链路再跑一遍。
  assert.equal(
    mock.findRequests("get", "fusion/status").length,
    1,
    `fusion/status 只应请求一次；实际：${joined}`,
  );
  // 只统计"创建工作台"本身：/generate 也挂在 /workspaces 下，必须精确匹配。
  const createPosts = calls.filter((r) => r.method === "post" && /\/workspaces$/.test(r.url));
  assert.equal(createPosts.length, 1, `创建工作台只应调用一次；实际：${joined}`);

  await unmount();
});

test("a real unmount stops late responses from starting new work", async () => {
  mock.reset();
  installHandlers();
  const { unmount } = await mount();
  await act(async () => { await sleep(10); });
  await unmount();
  const after1 = calls.length;
  await new Promise((r) => setTimeout(r, 250));
  assert.equal(calls.length, after1, `卸载后不应继续发起请求；实际新增：${calls.slice(after1).map((r) => r.url)}`);
});

test("StrictMode's double mount still creates exactly one workspace per course", async () => {
  // 允许两次调用发生，但服务端确定性幂等键 + 先查后建必须保证只建一个。
  mock.reset();
  installHandlers();
  const { unmount } = await mount();
  for (let i = 0; i < 30; i += 1) await act(async () => { await sleep(25); });

  // 精确匹配"创建工作台"本身：/generate 也以 /workspaces 开头。
  const posts = calls.filter((r) => r.method === "post" && /\/workspaces$/.test(r.url));
  assert.equal(posts.length, 1, `工作台只应创建一次；实际 ${posts.length} 次`);
  // 幂等键必须由课程派生，且每次完全相同（不含时间戳/随机量）。
  const key = posts[0].headers?.["Idempotency-Key"] || posts[0].headers?.["idempotency-key"];
  assert.equal(key, "magicclass-workspace-crs_x", `幂等键必须是课程派生值；实际 ${key}`);

  const gens = mock.findRequests("post", "/generate");
  assert.equal(gens.length, 1, `生成只应触发一次；实际 ${gens.length} 次`);
  assert.match(
    String(gens[0].headers?.["Idempotency-Key"] || ""),
    /^magicclass-stage-crs_x-[a-z0-9]+$/,
    "生成幂等键必须由课程 + 主题派生",
  );

  await unmount();
});

test("idempotency keys are deterministic and derived from the course, never the clock", async () => {
  const { stageGenerationIdempotencyKey, classroomEntryIdempotencyKey } = await import(
    "../src/features/magicclass/enterClassroomModel.js"
  );
  assert.equal(classroomEntryIdempotencyKey("crs_x"), "magicclass-workspace-crs_x");
  assert.equal(stageGenerationIdempotencyKey("crs_x", "t"), stageGenerationIdempotencyKey("crs_x", "t"));
  // 归一化空白后仍然一致，不会因为多一个空格就变成"新内容"。
  assert.equal(stageGenerationIdempotencyKey("crs_x", "t"), stageGenerationIdempotencyKey("crs_x", "  t  "));
  // 不同课程/不同主题必须不同，否则会错误地复用成同一份内容。
  assert.notEqual(stageGenerationIdempotencyKey("crs_x", "t"), stageGenerationIdempotencyKey("crs_y", "t"));
  assert.notEqual(stageGenerationIdempotencyKey("crs_x", "t"), stageGenerationIdempotencyKey("crs_x", "u"));
});

test("the default prompt carries authorized real course facts and synced chapters", async () => {
  const { buildClassroomPrompt } = await import("../src/features/magicclass/enterClassroomModel.js");
  const prompt = buildClassroomPrompt({
    name: "计算机科学概论",
    code: "CS101",
    semester: "2026秋",
    chapters: ["计算的历史与未来", "算法"],
    knowledgePoints: ["图灵机"],
    materials: ["第一讲讲义"],
  });
  assert.match(prompt, /计算机科学概论/);
  assert.match(prompt, /CS101/, "课程代码必须进入默认上下文");
  assert.match(prompt, /2026秋/, "学期必须进入默认上下文");
  assert.match(prompt, /计算的历史与未来/, "已同步章节必须进入默认上下文");
  assert.match(prompt, /图灵机/);
  assert.match(prompt, /第一讲讲义/, "已同步资料标题必须进入默认上下文");
});

test("chapters alone still count as synced, matching the backend", async () => {
  const { describeCourseReadiness, buildClassroomPrompt } = await import(
    "../src/features/magicclass/enterClassroomModel.js"
  );
  const onlyChapters = describeCourseReadiness({
    name: "军事理论", chapters: ["国防概述", "军事思想"],
    knowledgePoints: [], materials: [], warnings: [],
  });
  assert.equal(onlyChapters.synced, true, "仅有章节也属于已同步");
  assert.equal(onlyChapters.degraded, false);
  assert.doesNotMatch(onlyChapters.notice, /尚未同步/);

  const nothing = describeCourseReadiness({ name: "军事理论", chapters: [], knowledgePoints: [], materials: [], warnings: [] });
  assert.equal(nothing.synced, false);
  assert.match(nothing.notice, /课程资料尚未同步/);

  const failed = describeCourseReadiness({ name: "军事理论", chapters: [], knowledgePoints: [], materials: [], warnings: ["boom"] });
  assert.equal(failed.degraded, true, "读取失败必须与确实没有区分开");
  assert.match(failed.notice, /未能读取|稍后重试/);

  // 未同步时不得凭空造知识点。
  const prompt = buildClassroomPrompt({ name: "军事理论", chapters: [], knowledgePoints: [], materials: [] });
  assert.match(prompt, /围绕真实课程知识点组织讲解、示例、测验和练习/);
  assert.doesNotMatch(prompt, /知识点（/, "没有同步内容时不得列出编造的知识点");
});

test("the entry page shares one in-flight run instead of a one-shot flag", () => {
  const source = readFileSync(
    new URL("../src/pages/magicclassClassroomEntryPage.jsx", import.meta.url), "utf8",
  );
  assert.doesNotMatch(source, /started\.current/, "不得再用布尔量挡住第二次挂载（会再次卡死）");
  assert.match(source, /inFlight\.current/, "必须共享同一个在飞 Promise");
  // 在飞标记必须带课程归属，否则切换课程时 B 会误复用 A 的流程而永久卡住。
  assert.match(source, /inFlight\.current\.courseId === courseId/, "只允许复用同一门课的在飞流程");
});

// ===== A → B 课程切换竞态（用户复现的阻断） =====

test("switching courses mid-flight starts B immediately and never lets A continue", async () => {
  mock.reset();
  installHandlers();

  // A 的 context 请求挂起不返回：这正是"在途请求可观察"的条件。
  const gate = deferred();
  let holdA = true;
  mock.onGet("/courses/crs_a/magicclass-context", (config) => {
    if (!holdA) {
      return Promise.resolve({
        status: 200, config, headers: {},
        data: { course_id: "crs_a", name: "课程A", chapters: ["A章"], knowledge_points: [], materials: [], warnings: [], synced: true },
      });
    }
    return gate.promise.then((data) => ({ status: 200, config, headers: {}, data }));
  });

  const { host, go, unmount } = await mount("/courses/crs_a/classroom");

  // A 已经发出真实请求。
  await act(async () => { await sleep(60); });
  const aCalls = calls.map((r) => r.url).join(" | ");
  assert.ok(aCalls.includes("/courses/crs_a/magicclass-context"), `A 应已发起 context 请求；实际：${aCalls}`);

  // 不卸载组件，直接在同一 Router 内切到课程 B。
  calls.length = 0;
  await go("/courses/crs_b/classroom");
  holdA = false;

  // B 必须**立即**开始自己的链路，而不是等 A 的响应或另一个 effect。
  for (let i = 0; i < 40; i += 1) await act(async () => { await sleep(25); });

  const bUrls = calls.map((r) => r.url);
  const joined = bUrls.join(" | ");
  for (const step of ["/courses/crs_b/magicclass-context", "/magicclass/fusion/status", "/courses/crs_b/workspaces", "/generate"]) {
    assert.ok(joined.includes(step), `B 的链路缺少 ${step}；实际：${joined}`);
  }

  // 页面不得停在等待态上。
  assert.ok(
    !(host.textContent || "").includes("正在确认受管服务状态"),
    `切换到 B 后不得停在等待态；实际：${(host.textContent || "").slice(0, 200)}`,
  );

  // 释放 A 的响应后，A 不得再继续创建/生成。
  await act(async () => {
    gate.resolve({ course_id: "crs_a", name: "课程A", chapters: ["A章"], knowledge_points: [], materials: [], warnings: [], synced: true });
    await sleep(60);
  });
  calls.length = 0;
  await act(async () => { await sleep(300); });
  const stale = calls.filter((r) => r.url.includes("crs_a") && (r.method === "post"));
  assert.equal(stale.length, 0, `A 的迟到响应不得再创建/生成；实际：${stale.map((r) => r.url).join(" | ")}`);

  // A 不得产生任何写操作。
  const aWrites = mock.requests.filter(
    (r) => r.url.includes("crs_a") && r.method === "post",
  );
  assert.equal(aWrites.length, 0, `课程 A 不应产生写请求；实际：${aWrites.map((r) => r.url).join(" | ")}`);

  await unmount();
});

test("a real unmount stops late responses from creating, writing or re-polling", async () => {
  mock.reset();
  installHandlers();

  // 让生成返回一个"运行中"的任务，从而进入轮询；任务查询也挂起，便于观察迟到行为。
  const jobGate = deferred();
  let holdJob = true;
  mock.onPost("/courses/crs_x/workspaces/ws_1/generate", {
    job: { id: "job_1", status: "running", step: "generating_outlines", progress: 20 },
    stage_id: "st_1",
  });
  mock.onGet("/courses/crs_x/jobs/job_1", (config) => {
    if (!holdJob) {
      return Promise.resolve({ status: 200, config, headers: {}, data: { id: "job_1", status: "running", step: "generating_outlines", progress: 30 } });
    }
    return jobGate.promise.then((data) => ({ status: 200, config, headers: {}, data }));
  });

  const { unmount } = await mount("/courses/crs_x/classroom");
  for (let i = 0; i < 20; i += 1) await act(async () => { await sleep(25); });

  // 卸载（真实离开页面）。
  await unmount();
  calls.length = 0;

  // 释放迟到的响应，并等待远超过一次轮询间隔（800ms）的时间。
  jobGate.resolve({ id: "job_1", status: "completed", step: "completed", progress: 100 });
  holdJob = false;
  await act(async () => { await sleep(1500); });
  await new Promise((r) => setTimeout(r, 600));

  const after = calls.map((r) => `${r.method} ${r.url}`);
  assert.deepEqual(after, [], `卸载后不得再产生任何请求（含轮询）；实际：${after.join(" | ")}`);

  // 更重要的：不得产生任何写操作。
  const writes = mock.requests.filter((r) => r.method === "post");
  assert.equal(writes.length, 0, `卸载后不得再创建 workspace/stage；实际：${writes.map((r) => r.url).join(" | ")}`);
});

// ===== 课程简介进入默认 prompt =====

test("the authorized course description is included, length-capped and never invented", async () => {
  const { buildClassroomPrompt, describeCourseReadiness, DESCRIPTION_LIMIT } = await import(
    "../src/features/magicclass/enterClassroomModel.js"
  );

  // 真实简介必须出现在 prompt 中。
  const prompt = buildClassroomPrompt({
    name: "计算机科学概论",
    code: "CS101",
    semester: "2026秋",
    description: "面向大一新生的计算学科导论，介绍计算思维、算法与图灵机的基本概念。",
    chapters: ["计算的历史与未来"],
    knowledgePoints: [],
    materials: [],
  });
  assert.match(prompt, /课程简介：/);
  assert.match(prompt, /面向大一新生的计算学科导论/, "真实 description 必须进入 prompt");
  assert.match(prompt, /课程代码 CS101/);
  assert.match(prompt, /学期 2026秋/);

  // 限长：超长简介被截断到上限内，并以省略号标记被截断。
  const huge = "很长的课程简介。".repeat(200);
  const capped = buildClassroomPrompt({ name: "某课", description: huge, chapters: ["x"], knowledgePoints: [], materials: [] });
  const inside = capped.slice(capped.indexOf("课程简介：") + 5, capped.indexOf("。围绕"));
  assert.ok(inside.length <= DESCRIPTION_LIMIT + 1, `简介必须限长到 ${DESCRIPTION_LIMIT}，实际 ${inside.length}`);
  assert.match(capped, /…/, "被截断时必须可见地省略");

  // 空白归一化，且没有简介时不编造一句。
  const noDesc = buildClassroomPrompt({ name: "军事理论", chapters: [], knowledgePoints: [], materials: [] });
  assert.doesNotMatch(noDesc, /课程简介：/, "没有简介时不得编造简介");

  // readiness 同样暴露限长后的 description。
  const readiness = describeCourseReadiness({ name: "某课", description: huge, chapters: ["x"], knowledgePoints: [], materials: [] });
  assert.ok(readiness.description.length <= DESCRIPTION_LIMIT + 1);

  // 简介**不**算"已同步内容"：它是元信息，不是可讲解的课程资料。
  const descOnly = describeCourseReadiness({
    name: "只有简介的课", description: "一段真实简介", chapters: [], knowledgePoints: [], materials: [], warnings: [],
  });
  assert.equal(descOnly.synced, false, "只有简介不算资料已同步");
  assert.match(descOnly.notice, /课程资料尚未同步/);
});
