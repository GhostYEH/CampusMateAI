/**
 * 课程智能辅导空间（OpenMAIC 学生互动课堂）+ Web CPM 课程上下文契约测试。
 * 覆盖：5 种学生模式、进度展示、可安全内嵌判定（可信 host 白名单）、
 * 服务不可用隔离、问 CPM 携带 courseId、chatStream 发送 course_id、
 * CounselorPage 显示与清除课程上下文。
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

// 必须先于 api.js 加载，给 localStorage / location 提供确定性实现。
import "./helpers/setup-globals.mjs";
import * as apiModule from "../src/data/api.js";
import { createMockClient } from "./helpers/mock-client.mjs";

import * as C from "../src/data/interactiveClassroom.js";

const here = dirname(fileURLToPath(import.meta.url));
const read = (rel) => readFileSync(resolve(here, "..", rel), "utf8");
const REAL_FETCH = globalThis.fetch;

test.afterEach(() => {
  globalThis.fetch = REAL_FETCH;
});

// ===== 数据/逻辑模块：5 种模式与安全内嵌判定 =====

test("提供 5 种学生互动课堂模式且枚举合法", () => {
  assert.equal(C.INTERACTIVE_MODES.length, 5);
  const modes = C.INTERACTIVE_MODES.map((m) => m.mode);
  assert.deepEqual(modes, ["adaptive", "explain", "explore", "practice", "project"]);
  C.INTERACTIVE_MODES.forEach((m) => {
    assert.ok(typeof m.label === "string" && m.label.length > 0, `缺失中文名: ${m.mode}`);
    assert.ok(typeof m.description === "string" && m.description.length > 0, `缺失用途: ${m.mode}`);
  });
});

test("step 有完整阶段中文文案", () => {
  for (const key of ["queued", "analyzing", "outlining", "generating", "media", "voice", "saving", "done", "failed"]) {
    assert.ok(C.INTERACTIVE_STEP_LABELS[key], `缺 step 文案: ${key}`);
  }
  assert.equal(C.interactiveStepLabel("generating"), "生成场景");
  assert.equal(C.interactiveStepLabel("UNKNOWN"), "处理中");
});

test("可信 host 白名单默认空，未注入时任何课堂 url 都判定不可安全内嵌", () => {
  assert.deepEqual(C.DEFAULT_TRUSTED_EMBED_HOSTS, []);
  assert.equal(C.isTrustedEmbedUrl("https://openmaic.example.com/room/a"), false);
  assert.equal(C.isTrustedEmbedUrl(null, ["openmaic.example.com"]), false);
  assert.equal(C.isTrustedEmbedUrl("", ["openmaic.example.com"]), false);
});

test("注入可信 host 时精确/子域匹配才可内嵌，非可信与危险协议拒绝", () => {
  const hosts = ["openmaic.example.com"];
  assert.equal(C.isTrustedEmbedUrl("https://openmaic.example.com/rooms/1", hosts), true);
  assert.equal(C.isTrustedEmbedUrl("https://sub.openmaic.example.com/room", ["example.com"]), true);
  assert.equal(C.isTrustedEmbedUrl("https://evil.com/room", hosts), false);
  assert.equal(C.isTrustedEmbedUrl("javascript:alert(1)", hosts), false);
  assert.equal(C.isTrustedEmbedUrl("data:text/html,x", hosts), false);
});

// ===== 课程详情入口 =====

test("课程详情页出现智能辅导入口", () => {
  const page = read("src/pages/CourseDetailPage.jsx");
  assert.match(page, /\["mentoring",\s*"智能辅导"\]/, "缺少智能辅导 tab");
  assert.match(page, /<InteractiveClassroomPanel courseId=\{courseId\} \/>/, "未渲染互动课堂面板");
  assert.match(page, /import InteractiveClassroomPanel/, "未导入面板");
});

test("互动课堂面板提供 5 种学生模式与问 CPM 入口", () => {
  const panel = read("src/components/interactive/InteractiveClassroomPanel.jsx");
  assert.match(panel, /INTERACTIVE_MODES/, "面板未消费 5 模式数据");
  assert.match(panel, /INTERACTIVE_MODES\.map/, "未渲染模式选择");
  assert.match(panel, /roles?\w*\s*=\s*"radiogroup"/, "缺少模式 radiogroup 可访问语义");
});

// ===== 进度展示 =====

test("提交生成后展示来自后端的实时进度", () => {
  const panel = read("src/components/interactive/InteractiveClassroomPanel.jsx");
  assert.match(panel, /api\.generateInteractiveClassroom\(courseId/, "未调用生成接口");
  assert.match(panel, /api\.getInteractiveClassroomJob\(courseId/, "未轮询进度");
  assert.match(panel, /interactiveStepLabel\(/, "未展示 step 中文文案");
  assert.match(panel, /role="status"[^>]*aria-live="polite"/, "进度缺少无障碍状态");
});

test("失败展示可重试", () => {
  const panel = read("src/components/interactive/InteractiveClassroomPanel.jsx");
  assert.match(panel, /status === "failed"/, "未处理失败态");
  assert.match(panel, /retryCurrent/, "缺少重试入口");
});

// ===== 可安全内嵌判定 + 不可信不渲染 iframe =====

test("成功后在可信 host 下渲染课堂入口，不可信 url 不渲染 iframe", () => {
  const panel = read("src/components/interactive/InteractiveClassroomPanel.jsx");
  // iframe 只在 isTrustedEmbedUrl(session.url) 判定通过时才渲染
  assert.match(panel, /isTrustedEmbedUrl\(/, "面板未做 host 白名单校验");
  assert.match(panel, /<iframe[^>]*src=\{safeUrl\}/, "iframe 应绑定 safeUrl");
  assert.match(panel, /\{safeUrl \? <iframe/, "不可信时应走降级分支");
  assert.match(panel, /无法在此内嵌课堂/, "不可信时应有降级文案");
  assert.match(panel, /新窗口打开课堂/, "提供新窗口打开降级");
  assert.match(panel, /onClick=\{openInNewWindow\}/, "新窗口打开应只对可信 url 生效");
  assert.match(panel, /aria-label="智能辅导互动课堂"/, "iframe 缺少无障碍标签");
  assert.doesNotMatch(panel, /session\.url\]\s*<\/iframe>/, "不应使用未校验 url 直接内嵌");
});

// ===== 服务不可用隔离 =====

test("status 请求失败返回 enabled:false 而不抛错，不影响其它标签", async () => {
  const mock = createMockClient(apiModule.default);
  mock.reset();
  mock.onError("get", `/courses/c1/interactive-classroom/status`, 503, { detail: "OPENMAIC_NOT_ENABLED", code: "OPENMAIC_NOT_ENABLED" });
  const status = await apiModule.getInteractiveClassroomStatus("c1");
  assert.equal(status.enabled, false);
  assert.equal(status.unavailable, true);
});

test("面板对 enabled:false 渲染本地不可用态，不抛到整页", () => {
  const panel = read("src/components/interactive/InteractiveClassroomPanel.jsx");
  assert.match(panel, /!status\.enabled/, "未处理服务未开启分支");
  assert.match(panel, /enabled: false, loading: true/, "初始状态应为未启用");
  assert.match(panel, /status\.unavailable \? "辅导服务暂不可用"/, "未提供请求不可用文案");
  assert.match(panel, /这不影响课程其它内容/, "未声明隔离语义");
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
  mock.onGet("/courses/math/interactive-classroom/status", { enabled: true, service: "OpenMAIC", version: "v1" });
  mock.onPost("/courses/math/interactive-classroom/generate", { accepted: true, poll_interval_ms: 2000, mode: "adaptive", session: { session_id: "s1", status: "queued", step: "queued", progress: 0 } });
  mock.onGet("/courses/math/interactive-classroom/jobs/s1", { session: { session_id: "s1", status: "done", step: "done", progress: 100, url: "https://openmaic.example.com/room/x" } });
  mock.onGet("/courses/math/interactive-classroom", { enabled: true, items: [{ session_id: "s1", mode: "adaptive" }] });
  mock.onPost("/courses/math/interactive-classroom/s1/retry", { session: { session_id: "s1", status: "queued", mode: "adaptive" } });

  const status = await apiModule.getInteractiveClassroomStatus("math");
  assert.equal(status.enabled, true);
  assert.equal(status.service, "OpenMAIC");

  const created = await apiModule.generateInteractiveClassroom("math", { mode: "adaptive" });
  assert.equal(created.session.status, "queued");

  const job = await apiModule.getInteractiveClassroomJob("math", "s1");
  assert.equal(job.session.status, "done");

  const list = await apiModule.listInteractiveClassrooms("math");
  assert.equal(list.items.length, 1);

  const retried = await apiModule.retryInteractiveClassroom("math", "s1", { mode: "adaptive" });
  assert.equal(retried.session.mode, "adaptive");
});