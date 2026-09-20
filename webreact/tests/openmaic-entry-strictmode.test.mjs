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
    items: [{ id: "crs_x", name: "计算机科学概论", code: "CS101", semester: "2026秋" }],
  });
  mock.onGet("/courses/crs_x/openmaic-context", {
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
  mock.onGet("/openmaic/fusion/status", {
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
}

installHandlers();

const calls = mock.requests;

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
const { MemoryRouter, Routes, Route } = await import("react-router-dom");

const { default: OpenMAICClassroomEntryPage } = await vite.ssrLoadModule(
  "/src/pages/OpenMAICClassroomEntryPage.jsx",
);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** 挂载入口页（StrictMode 包裹），返回容器与卸载函数。 */
async function mount() {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(
      React.createElement(StrictMode, null,
        React.createElement(MemoryRouter, { initialEntries: ["/courses/crs_x/classroom"] },
          React.createElement(Routes, null,
            React.createElement(Route, {
              path: "/courses/:courseId/classroom",
              element: React.createElement(OpenMAICClassroomEntryPage),
            })))),
    );
  });
  return { host, unmount: () => act(async () => root.unmount()) };
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
  for (const step of ["openmaic-context", "fusion/status", "/workspaces", "/stages", "/generate"]) {
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
  assert.equal(key, "openmaic-workspace-crs_x", `幂等键必须是课程派生值；实际 ${key}`);

  const gens = mock.findRequests("post", "/generate");
  assert.equal(gens.length, 1, `生成只应触发一次；实际 ${gens.length} 次`);
  assert.match(
    String(gens[0].headers?.["Idempotency-Key"] || ""),
    /^openmaic-stage-crs_x-[a-z0-9]+$/,
    "生成幂等键必须由课程 + 主题派生",
  );

  await unmount();
});

test("idempotency keys are deterministic and derived from the course, never the clock", async () => {
  const { stageGenerationIdempotencyKey, classroomEntryIdempotencyKey } = await import(
    "../src/features/openmaic/enterClassroomModel.js"
  );
  assert.equal(classroomEntryIdempotencyKey("crs_x"), "openmaic-workspace-crs_x");
  assert.equal(stageGenerationIdempotencyKey("crs_x", "t"), stageGenerationIdempotencyKey("crs_x", "t"));
  // 归一化空白后仍然一致，不会因为多一个空格就变成"新内容"。
  assert.equal(stageGenerationIdempotencyKey("crs_x", "t"), stageGenerationIdempotencyKey("crs_x", "  t  "));
  // 不同课程/不同主题必须不同，否则会错误地复用成同一份内容。
  assert.notEqual(stageGenerationIdempotencyKey("crs_x", "t"), stageGenerationIdempotencyKey("crs_y", "t"));
  assert.notEqual(stageGenerationIdempotencyKey("crs_x", "t"), stageGenerationIdempotencyKey("crs_x", "u"));
});

test("the default prompt carries authorized real course facts and synced chapters", async () => {
  const { buildClassroomPrompt } = await import("../src/features/openmaic/enterClassroomModel.js");
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
    "../src/features/openmaic/enterClassroomModel.js"
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
    new URL("../src/pages/OpenMAICClassroomEntryPage.jsx", import.meta.url), "utf8",
  );
  assert.doesNotMatch(source, /started\.current/, "不得再用布尔量挡住第二次挂载（会再次卡死）");
  assert.match(source, /inFlight\.current/, "必须共享同一个在飞 Promise");
});
