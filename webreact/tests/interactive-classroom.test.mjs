/**
 * 课程智能辅导空间（OpenMAIC 学生互动课堂）行为测试。
 *
 * 关键点：成功课堂能否打开、不可信 Origin 是否降级，用**真实 React 渲染**
 * （vite ssrLoadModule + renderToStaticMarkup）验证，而不是读源码做正则断言。
 * 另覆盖：可信 Origin 按完整 URL.origin（含端口）精确比对、fail-closed 默认、
 * 真实生成步骤文案、进度/失败态、服务不可用隔离、问 CPM 携带 courseId。
 */
import test, { after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { createServer } from "vite";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

// 必须先于 api.js 加载，给 localStorage / location 提供确定性实现。
import "./helpers/setup-globals.mjs";
import * as apiModule from "../src/data/api.js";
import { createMockClient } from "./helpers/mock-client.mjs";

import * as C from "../src/data/interactiveClassroom.js";

const here = dirname(fileURLToPath(import.meta.url));
const read = (rel) => readFileSync(resolve(here, "..", rel), "utf8");
const REAL_FETCH = globalThis.fetch;

const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true },
  appType: "custom",
  logLevel: "silent",
});

after(async () => {
  globalThis.fetch = REAL_FETCH;
  await vite.close();
});

const { InteractiveClassroomView, interactiveErrorText } = await vite.ssrLoadModule(
  "/src/components/interactive/InteractiveClassroomPanel.jsx",
);

const TRUSTED = "http://127.0.0.1:3000";
const CLASSROOM_URL = `${TRUSTED}/classroom/room_ok`;

const enabledStatus = (overrides = {}) => ({
  enabled: true,
  configured: true,
  available: true,
  unavailable: false,
  loading: false,
  service: "openmaic",
  version: "1.0.0",
  embed_origin: TRUSTED,
  browser_embed_available: true,
  browser_embed_reason: null,
  ...overrides,
});

/** 真实渲染面板展示层，返回 HTML 字符串。 */
const renderPanel = (props = {}) =>
  renderToStaticMarkup(
    createElement(InteractiveClassroomView, {
      status: enabledStatus(),
      ...props,
    }),
  );

// ===== 数据模块：5 种模式与真实步骤文案 =====

test("提供 5 种学生互动课堂模式且枚举合法", () => {
  assert.equal(C.INTERACTIVE_MODES.length, 5);
  assert.deepEqual(
    C.INTERACTIVE_MODES.map((m) => m.mode),
    ["adaptive", "explain", "explore", "practice", "project"],
  );
  C.INTERACTIVE_MODES.forEach((m) => {
    assert.ok(typeof m.label === "string" && m.label.length > 0, `缺失中文名: ${m.mode}`);
    assert.ok(typeof m.description === "string" && m.description.length > 0, `缺失用途: ${m.mode}`);
  });
});

test("step 文案覆盖 OpenMAIC 真实生成步骤与 queued/failed", () => {
  const real = [
    "queued",
    "initializing",
    "researching",
    "generating_outlines",
    "generating_scenes",
    "generating_media",
    "generating_tts",
    "persisting",
    "completed",
    "failed",
  ];
  for (const key of real) {
    assert.ok(C.INTERACTIVE_STEP_LABELS[key], `缺 step 文案: ${key}`);
  }
  assert.equal(C.interactiveStepLabel("generating_tts"), "生成语音讲解");
  assert.equal(C.interactiveStepLabel("generating_outlines"), "生成教学大纲");
  assert.equal(C.interactiveStepLabel("persisting"), "保存课堂");
  assert.equal(C.interactiveStepLabel("completed"), "已完成");
  assert.equal(C.interactiveStepLabel("UNKNOWN"), "处理中");
  // 旧的臆造阶段名不应再出现
  for (const stale of ["analyzing", "outlining", "media", "voice", "saving", "done"]) {
    assert.equal(C.INTERACTIVE_STEP_LABELS[stale], undefined, `残留旧阶段文案: ${stale}`);
  }
});

test("isSessionLive 只在非终态为真", () => {
  assert.equal(C.isSessionLive({ status: "queued" }), true);
  assert.equal(C.isSessionLive({ status: "running" }), true);
  assert.equal(C.isSessionLive({ status: "succeeded" }), false);
  assert.equal(C.isSessionLive({ status: "failed" }), false);
  assert.equal(C.isSessionLive(null), false);
});

// ===== 可信 Origin：完整 origin 精确校验（含端口） =====

test("默认白名单为空，未拿到可信 Origin 时任何课堂 url 都不可信（fail-closed）", () => {
  assert.deepEqual(C.DEFAULT_TRUSTED_EMBED_ORIGINS, []);
  assert.equal(C.isTrustedEmbedUrl(CLASSROOM_URL), false);
  assert.equal(C.isTrustedEmbedUrl(CLASSROOM_URL, []), false);
  assert.equal(C.isTrustedEmbedUrl(null, [TRUSTED]), false);
  assert.equal(C.isTrustedEmbedUrl("", [TRUSTED]), false);
});

test("可信判定按完整 origin 精确比对，端口不同即不可信", () => {
  const origins = [TRUSTED];
  assert.equal(C.isTrustedEmbedUrl(CLASSROOM_URL, origins), true);
  // 端口不同 -> 不可信（不能退化成 host 后缀匹配）
  assert.equal(C.isTrustedEmbedUrl("http://127.0.0.1:30000/classroom/x", origins), false);
  assert.equal(C.isTrustedEmbedUrl("http://127.0.0.1:3001/classroom/x", origins), false);
  assert.equal(C.isTrustedEmbedUrl("http://127.0.0.1/classroom/x", origins), false);
  // scheme 不同 -> 不可信
  assert.equal(C.isTrustedEmbedUrl("https://127.0.0.1:3000/classroom/x", origins), false);
  // 子域 / 其它主机 -> 不可信
  assert.equal(C.isTrustedEmbedUrl("http://evil.example.com/classroom/x", origins), false);
  assert.equal(C.isTrustedEmbedUrl("http://127.0.0.1.evil.com:3000/classroom/x", origins), false);
  // 危险协议
  assert.equal(C.isTrustedEmbedUrl("javascript:alert(1)", origins), false);
  assert.equal(C.isTrustedEmbedUrl("data:text/html,x", origins), false);
  assert.equal(C.isTrustedEmbedUrl("file:///etc/passwd", origins), false);
});

test("白名单条目会归一化为 origin，非法条目被丢弃", () => {
  assert.deepEqual(C.normalizeTrustedOrigins([`${TRUSTED}/classroom/room_ok`]), [TRUSTED]);
  assert.deepEqual(C.normalizeTrustedOrigins(["javascript:alert(1)", "", "  ", null]), []);
  assert.deepEqual(C.normalizeTrustedOrigins([TRUSTED, TRUSTED]), [TRUSTED]);
});

test("trustedOriginsFromStatus 只认后端返回的 embed_origin", () => {
  assert.deepEqual(C.trustedOriginsFromStatus({ embed_origin: TRUSTED }), [TRUSTED]);
  assert.deepEqual(C.trustedOriginsFromStatus({ embed_origin: null }), []);
  assert.deepEqual(C.trustedOriginsFromStatus({}), []);
  assert.deepEqual(C.trustedOriginsFromStatus(null), []);
  assert.deepEqual(C.trustedOriginsFromStatus({ embed_origin: "not a url" }), []);
});

// ===== 真实 React 渲染：成功课堂能打开 =====

test("成功课堂在可信 Origin 下真实渲染出 iframe 与新窗口入口", () => {
  const markup = renderPanel({
    session: {
      session_id: "s1",
      status: "succeeded",
      step: "completed",
      progress: 100,
      url: CLASSROOM_URL,
      scenes_count: 6,
    },
  });
  assert.match(markup, /<iframe[^>]*class="interactive-frame"/, "应渲染内嵌课堂 iframe");
  assert.match(
    markup,
    new RegExp(`<iframe[^>]*src="${CLASSROOM_URL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}"`),
    "iframe src 必须是后端下发的课堂地址",
  );
  assert.match(markup, /aria-label="智能辅导互动课堂"/);
  assert.match(markup, /新窗口打开课堂/);
  assert.doesNotMatch(markup, /无法在此内嵌课堂/, "可信地址不应走降级分支");
});

test("成功课堂的 iframe 在 React 中被沙箱约束", () => {
  const markup = renderPanel({
    session: { session_id: "s1", status: "succeeded", step: "completed", url: CLASSROOM_URL },
  });
  assert.match(markup, /sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-downloads"/);
});

test("ACCESS_CODE 仅后端认证时禁止浏览器内嵌和生成不可访问的课堂", () => {
  const markup = renderPanel({
    status: enabledStatus({
      browser_embed_available: false,
      browser_embed_reason: "目标互动课堂启用了独立访问保护，CampusMate 不会把访问码发送到浏览器。",
    }),
    session: { session_id: "s1", status: "succeeded", step: "completed", url: CLASSROOM_URL },
  });
  assert.doesNotMatch(markup, /<iframe/);
  assert.doesNotMatch(markup, /开始生成/);
  assert.match(markup, /课堂浏览授权尚未配置/);
  assert.match(markup, /不会把访问码发送到浏览器/);
});

test("Origin 不匹配时真实渲染为降级态且不出现 iframe", () => {
  const markup = renderPanel({
    status: enabledStatus({ embed_origin: "http://127.0.0.1:9999" }),
    session: { session_id: "s1", status: "succeeded", step: "completed", url: CLASSROOM_URL },
  });
  assert.doesNotMatch(markup, /<iframe/, "不可信 Origin 绝不能渲染 iframe");
  assert.match(markup, /无法在此内嵌课堂/);
  assert.match(markup, /已阻止打开/);
});

test("后端未下发可信 Origin 时真实渲染为降级态（fail-closed）", () => {
  const markup = renderPanel({
    status: { enabled: true, loading: false, service: "openmaic" },
    session: { session_id: "s1", status: "succeeded", step: "completed", url: CLASSROOM_URL },
  });
  assert.doesNotMatch(markup, /<iframe/);
  assert.match(markup, /无法在此内嵌课堂/);
});

test("历史课堂列表里可信地址渲染成可打开的链接", () => {
  const markup = renderPanel({
    items: [
      { session_id: "s1", mode: "explain", url: CLASSROOM_URL, scenes_count: 6 },
      { session_id: "s2", mode: "adaptive", url: "http://evil.example.com/classroom/x" },
    ],
  });
  assert.match(markup, new RegExp(`<a[^>]*href="${CLASSROOM_URL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}"`));
  assert.match(markup, /target="_blank"/);
  assert.match(markup, /rel="noopener noreferrer"/);
  assert.match(markup, /aria-label="打开互动课堂"/);
  assert.match(markup, />打开</);
  // 不可信的历史课堂只能显示为不可打开
  assert.doesNotMatch(markup, /href="http:\/\/evil\.example\.com/);
  assert.match(markup, /待打开/);
  assert.match(markup, /概念讲解/);
});

test("显式注入可信 Origin 时以注入值为准（空数组=完全禁止）", () => {
  const trusted = renderPanel({
    trustedEmbedOrigins: [TRUSTED],
    status: { enabled: true, loading: false },
    session: { session_id: "s1", status: "succeeded", step: "completed", url: CLASSROOM_URL },
  });
  assert.match(trusted, /<iframe/);

  const denied = renderPanel({
    trustedEmbedOrigins: [],
    session: { session_id: "s1", status: "succeeded", step: "completed", url: CLASSROOM_URL },
  });
  assert.doesNotMatch(denied, /<iframe/);
});

// ===== 真实 React 渲染：进度 / 失败 / 不可用 =====

test("进行中真实渲染出 step 中文文案与进度", () => {
  const markup = renderPanel({
    session: {
      session_id: "s1",
      status: "running",
      step: "generating_tts",
      progress: 62,
      message: "正在生成语音讲解",
    },
  });
  assert.match(markup, /role="status"[^>]*aria-live="polite"/);
  assert.match(markup, /生成语音讲解/);
  assert.match(markup, /62%/);
  assert.match(markup, /正在生成语音讲解/);
  assert.doesNotMatch(markup, /<iframe/);
});

test("失败态真实渲染出错误信息与重试入口", () => {
  const markup = renderPanel({
    session: { session_id: "s1", status: "failed", step: "failed", error: "场景生成失败" },
  });
  assert.match(markup, /role="alert"/);
  assert.match(markup, /场景生成失败/);
  assert.match(markup, /重新生成/);
});

test("失败态优先展示服务端 error，字符串错误不会被通用文案覆盖", () => {
  assert.equal(interactiveErrorText("场景生成失败", "通用失败"), "场景生成失败");
  const markup = renderPanel({
    session: {
      session_id: "s1",
      status: "failed",
      step: "failed",
      message: "生成失败",
      error: "场景 3 的可视化生成超时",
    },
  });
  assert.match(markup, /场景 3 的可视化生成超时/);
  assert.doesNotMatch(markup, />生成失败</);
});

test("服务不可用时真实渲染隔离态，不抛到整页", () => {
  const markup = renderPanel({
    status: { enabled: false, unavailable: true, loading: false, reason: "互动课堂服务暂不可用" },
  });
  assert.match(markup, /辅导服务暂不可用/);
  assert.match(markup, /这不影响课程其它内容/);
  assert.doesNotMatch(markup, /<iframe/);
});

test("服务未配置时真实渲染未开启态", () => {
  const markup = renderPanel({
    status: { enabled: false, unavailable: false, loading: false },
  });
  assert.match(markup, /本课程尚未开启智能辅导/);
  assert.match(markup, /重新检测/);
});

test("模式选择器有 radiogroup 可访问语义", () => {
  const markup = renderPanel();
  assert.match(markup, /role="radiogroup"[^>]*aria-label="选择辅导模式"/);
  assert.match(markup, /aria-pressed="true"/);
  assert.match(markup, /开始生成 自适应课堂/);
});

// ===== 课程详情入口（接线断言） =====

test("课程详情页出现智能辅导入口", () => {
  const page = read("src/pages/CourseDetailPage.jsx");
  assert.match(page, /\["mentoring",\s*"智能辅导"\]/, "缺少智能辅导 tab");
  assert.match(page, /<InteractiveClassroomPanel courseId=\{courseId\} \/>/, "未渲染互动课堂面板");
  assert.match(page, /import InteractiveClassroomPanel/, "未导入面板");
});

// ===== 服务不可用隔离（api 层） =====

test("status 请求失败返回 enabled:false 而不抛错，不影响其它标签", async () => {
  const mock = createMockClient(apiModule.default);
  mock.reset();
  mock.onError("get", `/courses/c1/interactive-classroom/status`, 503, {
    detail: "OPENMAIC_NOT_ENABLED",
    code: "OPENMAIC_NOT_ENABLED",
  });
  const status = await apiModule.getInteractiveClassroomStatus("c1");
  assert.equal(status.enabled, false);
  assert.equal(status.unavailable, true);
});

// ===== 问 CPM 携带 courseId =====

test("问 CPM 使用 query 参数携带 courseId", () => {
  const panel = read("src/components/interactive/InteractiveClassroomPanel.jsx");
  assert.match(panel, /params\.set\("course", courseId\)/, "未写入 course 参数");
  assert.match(panel, /navigate\(`\/counselor\?\$\{params\.toString\(\)\}`\)/, "未携带 query 跳转 CPM");
  assert.match(panel, /问 CPM/, "缺少问 CPM 入口");
});

// ===== chatStream 发送 course_id =====

test("chatStream 在请求体中发送 course_id", () => {
  const api = read("src/data/api.js");
  assert.match(api, /courseId = null/, "chatStream 缺少 courseId 选项");
  assert.match(api, /course_id: courseId/, "请求体未携带 course_id 字段");
});

test("调用 chatStream 含 courseId 时实际发送 course_id", async () => {
  let captured = null;
  globalThis.fetch = async (url, options) => {
    captured = { url: String(url), body: JSON.parse(options.body) };
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("data: {\"ok\":1}\n\nevent: done\ndata: {\"ok\":1}\n\n"));
        controller.close();
      },
    });
    return { ok: true, status: 200, headers: {}, body: stream };
  };
  let done = false;
  await apiModule.chatStream("为这门课安排复习", { courseId: "coursemath101", onDone: () => { done = true; } });
  assert.match(captured.url, /\/counselor\/chat$/);
  assert.equal(captured.body.course_id, "coursemath101");
  assert.equal(captured.body.message, "为这门课安排复习");
  assert.equal(done, true);
});

test("无 courseId 时不发送 course_id 字段", async () => {
  let captured = null;
  globalThis.fetch = async (_url, options) => {
    captured = JSON.parse(options.body);
    const stream = new ReadableStream({
      start(controller) { controller.enqueue(new TextEncoder().encode("event: done\ndata: {}\n\n")); controller.close(); },
    });
    return { ok: true, status: 200, headers: {}, body: stream };
  };
  await apiModule.chatStream("你好", {});
  assert.equal("course_id" in captured, false);
});

// ===== CounselorPage 课程上下文 =====

test("CounselorPage 从 URL 读取 courseId 并展示/清除课程上下文", () => {
  const page = read("src/pages/CounselorPage.jsx");
  assert.match(page, /\.get\("course"\)/, "未读取 course 查询参数");
  assert.match(page, /\.get\("prompt"\)/, "未读取 prompt 查询参数");
  assert.match(page, /当前正在辅导：\{courseName/, "缺少课程上下文标签");
  assert.match(page, /退出课程辅导/, "缺少退出课程上下文入口");
  assert.match(page, /exitCourseContext/, "未清除课程上下文");
  assert.match(page, /courseId: courseId \|\| undefined/, "对话未携带 courseId 上下文");
});

test("课程上下文下提供基于课程的动态推荐问题（不硬编码掌握状态）", () => {
  const page = read("src/pages/CounselorPage.jsx");
  assert.match(page, /courseContextSuggestions/, "缺少课程推荐问题组");
  assert.match(page, /courseId \? courseContextSuggestions : suggestions/, "未按课程上下文切换推荐");
  for (const q of ["讲解这门课当前最重要的知识点", "根据我的掌握情况安排复习", "帮我设计一次可视化学习", "为这门课生成自测", "哪些内容适合用互动课堂学习"]) {
    assert.ok(page.includes(q), `缺失课程推荐问题：${q}`);
  }
});

// ===== 互动课堂后端接口契约 =====

test("互动课堂后端接口路径符合契约", async () => {
  const mock = createMockClient(apiModule.default);
  mock.reset();
  mock.onGet("/courses/math/interactive-classroom/status", {
    enabled: true,
    configured: true,
    available: true,
    service: "openmaic",
    version: "v1",
    embed_origin: TRUSTED,
  });
  mock.onPost("/courses/math/interactive-classroom/generate", {
    accepted: true,
    poll_interval_ms: 2000,
    mode: "adaptive",
    session: { session_id: "s1", status: "queued", step: "queued", progress: 0 },
  });
  mock.onGet("/courses/math/interactive-classroom/jobs/s1", {
    session: { session_id: "s1", status: "succeeded", step: "completed", progress: 100, url: CLASSROOM_URL },
  });
  mock.onGet("/courses/math/interactive-classroom", {
    enabled: true,
    items: [{ session_id: "s1", mode: "adaptive", url: CLASSROOM_URL }],
  });
  mock.onPost("/courses/math/interactive-classroom/s1/retry", {
    session: { session_id: "s1", status: "queued", mode: "adaptive" },
  });

  const status = await apiModule.getInteractiveClassroomStatus("math");
  assert.equal(status.enabled, true);
  assert.equal(status.embed_origin, TRUSTED);

  const created = await apiModule.generateInteractiveClassroom("math", { mode: "adaptive" });
  assert.equal(created.session.status, "queued");

  const job = await apiModule.getInteractiveClassroomJob("math", "s1");
  assert.equal(job.session.status, "succeeded");
  assert.equal(C.isTrustedEmbedUrl(job.session.url, C.trustedOriginsFromStatus(status)), true);

  const list = await apiModule.listInteractiveClassrooms("math");
  assert.equal(list.items.length, 1);

  const retried = await apiModule.retryInteractiveClassroom("math", "s1", { mode: "adaptive" });
  assert.equal(retried.session.mode, "adaptive");
});
