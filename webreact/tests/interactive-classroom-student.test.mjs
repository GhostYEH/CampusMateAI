/**
 * 阶段 4 —— Web 课程详情"智能辅导"学生化行为测试。
 *
 * 关键点：用**真实 React 渲染**（vite ssrLoadModule + renderToStaticMarkup）验证
 * 学生实际看到什么，而不是读源码做正则断言。覆盖：
 * - 9 个生成意图 + 旧值归一化；
 * - 6 种服务状态各有独立文案；
 * - 生成前必须展示课程/资料/推荐理由/"形态只是意图"；
 * - 真实组成只来自 composition 回读，绝不根据请求形态推断；
 * - composition 读取失败要明说失败，不能显示成"这节课没有内容"；
 * - 同源课堂地址一律拒绝内嵌；
 * - 进度区不提供取消、不展示 MP4。
 */
import test, { after } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import "./helpers/setup-globals.mjs";
import * as apiModule from "../src/data/api.js";
import { createMockClient } from "./helpers/mock-client.mjs";

import * as C from "../src/data/interactiveClassroom.js";

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

const { InteractiveClassroomView } = await vite.ssrLoadModule(
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
  compatibility: "compatible",
  degraded: false,
  unavailable_capabilities: [],
  service: "magicclass",
  version: "1.0.1",
  embed_origin: TRUSTED,
  browser_embed_available: true,
  browser_embed_reason: null,
  external_3d_available: true,
  ...overrides,
});

const render = (props = {}) =>
  renderToStaticMarkup(
    createElement(InteractiveClassroomView, { status: enabledStatus(), ...props }),
  );

// ===== 意图与旧值 =====

test("旧值 explore/practice/project 归一化到规范意图", () => {
  assert.equal(C.normalizeMode("explore"), "simulation");
  assert.equal(C.normalizeMode("practice"), "quiz");
  assert.equal(C.normalizeMode("project"), "pbl");
  assert.equal(C.normalizeMode("  REVIEW "), "review");
  assert.equal(C.normalizeMode(""), "adaptive");
  assert.equal(C.normalizeMode("nonsense"), "adaptive");
  assert.deepEqual(C.LEGACY_MODE_ALIASES, {
    explore: "simulation",
    practice: "quiz",
    project: "pbl",
  });
});

test("意图声明文案明确说明形态不保证产出", () => {
  assert.match(C.MODE_INTENT_NOTE, /生成意图/);
  assert.match(C.MODE_INTENT_NOTE, /决定/);
});

// ===== 状态机 =====

test("七种服务状态各有独立状态与文案", () => {
  assert.equal(C.classroomState({ loading: true }), C.CLASSROOM_STATES.LOADING);
  assert.equal(
    C.classroomState({ enabled: false, unavailable: false }),
    C.CLASSROOM_STATES.NOT_CONFIGURED,
  );
  assert.equal(
    C.classroomState({ enabled: false, unavailable: true }),
    C.CLASSROOM_STATES.UNAVAILABLE,
  );
  assert.equal(
    C.classroomState({ enabled: false, incompatible: true }),
    C.CLASSROOM_STATES.INCOMPATIBLE,
  );
  assert.equal(
    C.classroomState({ enabled: true, browser_embed_available: false }),
    C.CLASSROOM_STATES.EMBED_BLOCKED,
  );
  assert.equal(
    C.classroomState({ configured: true, available: false }),
    C.CLASSROOM_STATES.CONFIGURED,
  );
  assert.equal(C.classroomState(enabledStatus()), C.CLASSROOM_STATES.READY);
  for (const key of Object.values(C.CLASSROOM_STATES)) {
    assert.ok(C.CLASSROOM_STATE_TEXT[key]?.title, `缺状态文案: ${key}`);
  }
  assert.equal(C.canGenerateInState(C.CLASSROOM_STATES.READY), true);
  assert.equal(C.canGenerateInState(C.CLASSROOM_STATES.CONFIGURED), false);
  assert.equal(C.canGenerateInState(C.CLASSROOM_STATES.INCOMPATIBLE), false);
});

test("unavailable 优先于 configured（与 Android 同一份 DTO 的语义对齐）", () => {
  // 真实后端组合：配置了但连不上。显示"尚未开启"或"已配置，正在准备"都是错的。
  assert.equal(
    C.classroomState({ configured: true, available: false, unavailable: true }),
    C.CLASSROOM_STATES.UNAVAILABLE,
  );
  // incompatible 优先于一切
  assert.equal(
    C.classroomState({
      configured: true,
      available: false,
      unavailable: true,
      incompatible: true,
      degraded: true,
    }),
    C.CLASSROOM_STATES.INCOMPATIBLE,
  );
  // 降级但可用仍然是"可用"（后端 degraded 只在 available=true 时有意义）
  assert.equal(
    C.classroomState({
      enabled: true,
      configured: true,
      available: true,
      degraded: true,
      browser_embed_available: true,
    }),
    C.CLASSROOM_STATES.READY,
  );
});

test("穷尽真实 DTO 组合：每个组合都映射到确定状态", () => {
  const expected = (s) => {
    if (s.incompatible === true || s.compatibility === "incompatible") {
      return C.CLASSROOM_STATES.INCOMPATIBLE;
    }
    if (s.unavailable === true) return C.CLASSROOM_STATES.UNAVAILABLE;
    if (s.enabled) {
      return s.browser_embed_available === false
        ? C.CLASSROOM_STATES.EMBED_BLOCKED
        : C.CLASSROOM_STATES.READY;
    }
    if (s.configured === true || s.available === true || s.degraded === true) {
      return C.CLASSROOM_STATES.CONFIGURED;
    }
    return C.CLASSROOM_STATES.NOT_CONFIGURED;
  };
  let checked = 0;
  for (let mask = 0; mask < 32; mask += 1) {
    const status = {
      configured: (mask & 1) !== 0,
      available: (mask & 2) !== 0,
      unavailable: (mask & 4) !== 0,
      incompatible: (mask & 8) !== 0,
      degraded: (mask & 16) !== 0,
    };
    assert.equal(
      C.classroomState(status),
      expected(status),
      `组合 ${JSON.stringify(status)} 的状态必须确定`,
    );
    checked += 1;
  }
  assert.equal(checked, 32);
});

test("版本不兼容时真实渲染不兼容提示且不给生成入口", () => {
  const markup = render({
    status: enabledStatus({
      enabled: false,
      incompatible: true,
      compatibility: "incompatible",
      compatibility_reason: "目标互动课堂服务的接口契约与预期不一致",
    }),
  });
  assert.match(markup, /辅导服务版本不兼容/);
  assert.match(markup, /请联系管理员核对部署版本/);
  assert.doesNotMatch(markup, /<iframe/);
  assert.doesNotMatch(markup, /确认生成/);
});

test("部分能力降级时给出明确提示但仍可生成", () => {
  const markup = render({
    status: enabledStatus({ degraded: true, unavailable_capabilities: ["tts", "imageGeneration"] }),
  });
  assert.match(markup, /部分能力当前不可用/);
  assert.match(markup, /tts/);
  assert.match(markup, /仍可生成其它形式的内容/);
  assert.match(markup, /查看这次会生成什么/);
});

test("3D 外部依赖不可用时给出显式降级提示", () => {
  const markup = render({ status: enabledStatus({ external_3d_available: false }) });
  assert.match(markup, /无法访问外部 3D 资源/);
  assert.match(markup, /3D\/可视化形态不可用/);
});

// ===== 生成前确认 =====

test("生成前展示课程、资料、推荐理由与意图声明，并要求点击确认", () => {
  const markup = render({
    mode: "adaptive",
    plan: {
      course_id: "c1",
      course_name: "高等数学",
      mode: "review",
      mode_label: "考前复习",
      requested_mode: "adaptive",
      adaptive_reason: "你在「极限」等 2 个知识点上掌握不足，且 9 天后有期中考试。",
      materials: [
        { id: "m1", title: "第3章讲义", kind: "document" },
        { id: "m2", title: "极限习题", kind: "document" },
      ],
      context_warnings: ["考试读取失败，已省略(OperationalError)"],
    },
  });
  assert.match(markup, /生成前请确认/);
  assert.match(markup, /高等数学/);
  assert.match(markup, /为什么推荐/);
  assert.match(markup, /9 天后有期中考试/);
  assert.match(markup, /第3章讲义/);
  assert.match(markup, /使用哪些课程资料/);
  assert.match(markup, /生成意图/);
  assert.match(markup, /确认生成 考前复习/);
  // 上下文读取失败必须让学生看到
  assert.match(markup, /考试读取失败/);
});

test("没有资料时如实说明，而不是编造材料", () => {
  const markup = render({
    plan: {
      course_id: "c1",
      course_name: "线性代数",
      mode: "explain",
      mode_label: "概念讲解",
      materials: [],
    },
  });
  assert.match(markup, /没有已同步的可用资料/);
});

// ===== 真实组成 =====

test("真实组成来自 composition 回读，不根据请求形态推断", () => {
  // 请求的是"思维导图"，但真实产出只有幻灯片与测验 —— 必须如实展示真实结果
  const markup = render({
    mode: "mindmap",
    session: { session_id: "s1", status: "succeeded", step: "completed", url: CLASSROOM_URL },
    composition: {
      classroom_id: "room_ok",
      scene_total: 4,
      scenes: [
        { type: "slide", count: 3 },
        { type: "quiz", count: 1 },
      ],
      widget_types: [],
      has_whiteboard: true,
      has_tts: false,
      has_multi_agent: false,
      error: null,
    },
  });
  assert.match(markup, /已生成内容包含：幻灯片 ×3、测验 ×1/);
  assert.match(markup, /白板推导/);
  assert.doesNotMatch(markup, /思维导图 ×/);
});

test("未知类型安全降级展示，不崩溃也不冒充已知类型", () => {
  const markup = render({
    session: { session_id: "s1", status: "succeeded", step: "completed", url: CLASSROOM_URL },
    composition: {
      classroom_id: "room_ok",
      scene_total: 1,
      scenes: [{ type: "hologram", count: 1 }],
      widget_types: [{ widget_type: "quantum-sandbox", count: 1 }],
      error: null,
    },
  });
  assert.match(markup, /未知类型（hologram）/);
  assert.match(markup, /未知形式（quantum-sandbox）/);
});

test("composition 读取失败时明说失败，不显示成空内容", () => {
  const markup = render({
    session: { session_id: "s1", status: "succeeded", step: "completed", url: CLASSROOM_URL },
    compositionError: "课堂内容读取失败(MagicClassUnavailable)",
  });
  assert.match(markup, /课堂内容读取失败/);
  assert.doesNotMatch(markup, /这节课没有生成可展示的内容/);
});

test("后端返回带 error 的 composition 时同样明说失败", () => {
  const markup = render({
    session: { session_id: "s1", status: "succeeded", step: "completed", url: CLASSROOM_URL },
    composition: { classroom_id: "room_ok", scene_total: 0, error: "课堂响应结构异常" },
  });
  assert.match(markup, /课堂内容读取失败：课堂响应结构异常/);
});

test("课堂含 3D 而环境不可达时按降级提示，不报整节课失败", () => {
  const markup = render({
    session: { session_id: "s1", status: "succeeded", step: "completed", url: CLASSROOM_URL },
    composition: {
      classroom_id: "room_ok",
      scene_total: 1,
      scenes: [{ type: "interactive", count: 1 }],
      widget_types: [{ widget_type: "visualization3d", count: 1 }],
      requires_external_3d: true,
      external_3d_available: false,
      degraded: true,
      error: null,
    },
  });
  assert.match(markup, /包含 3D 内容/);
  assert.match(markup, /可能打不开/);
  assert.doesNotMatch(markup, /课堂生成失败/);
});

// ===== 同源拒绝 =====

test("同源课堂地址一律拒绝内嵌（allow-same-origin 失去隔离意义）", () => {
  const page = C.pageOrigin();
  const sameOriginUrl = `${page}/classroom/room_x`;
  // 同源地址即使被后端放进白名单也不可信
  assert.equal(C.isTrustedEmbedUrl(sameOriginUrl, [page]), true);
  assert.equal(C.isSafeClassroomUrl(sameOriginUrl, [page]), false);

  const markup = render({
    trustedEmbedOrigins: [page],
    session: { session_id: "s1", status: "succeeded", step: "completed", url: sameOriginUrl },
  });
  assert.doesNotMatch(markup, /<iframe/);
  assert.match(markup, /同源/);
});

// ===== 进度 / 失败 =====

test("进度区展示真实 step、更新时间，且不提供取消按钮", () => {
  const markup = render({
    polling: true,
    session: {
      session_id: "s1",
      status: "running",
      step: "generating_media",
      progress: 45,
      message: "正在生成图片",
      updated_at: "2026-09-16T10:00:00+00:00",
    },
  });
  assert.match(markup, /生成图片与视频/);
  assert.match(markup, /45%/);
  assert.match(markup, /最近更新/);
  assert.match(markup, /停止查看进度/);
  // 不存在"取消"语义（magic class 没有 cancel 端点，不能给学生假按钮）
  assert.doesNotMatch(markup, />取消</);
});

test("失败态展示稳定错误码与重试入口", () => {
  const markup = render({
    session: {
      session_id: "s1",
      status: "failed",
      step: "failed",
      error: "场景 3 生成超时",
      error_code: "MAGICCLASS_GENERATION_FAILED",
      retryable: true,
    },
  });
  assert.match(markup, /role="alert"/);
  assert.match(markup, /场景 3 生成超时/);
  assert.match(markup, /MAGICCLASS_GENERATION_FAILED/);
  assert.match(markup, /重新生成/);
});

test("部分完成时给出可执行提示", () => {
  const markup = render({
    session: {
      session_id: "s1",
      status: "succeeded",
      step: "completed",
      url: CLASSROOM_URL,
      partial: true,
    },
    composition: { classroom_id: "room_ok", scene_total: 1, scenes: [{ type: "slide", count: 1 }] },
  });
  assert.match(markup, /部分内容没有生成成功/);
});

// ===== 不实现的按钮不出现 =====

test("不展示 MP4 导出，也不展示未实现的归档/删除按钮", () => {
  const markup = render({
    session: { session_id: "s1", status: "succeeded", step: "completed", url: CLASSROOM_URL },
    composition: { classroom_id: "room_ok", scene_total: 1, scenes: [{ type: "slide", count: 1 }] },
  });
  assert.doesNotMatch(markup, /MP4/);
  assert.doesNotMatch(markup, /导出视频/);
  assert.doesNotMatch(markup, /归档/);
  assert.doesNotMatch(markup, /删除课堂/);
});

// ===== API 契约 =====

test("plan 与 composition 的后端接口路径符合契约", async () => {
  const mock = createMockClient(apiModule.default);
  mock.reset();
  mock.onGet("/courses/math/interactive-classroom/plan?mode=review", {
    course_id: "math",
    course_name: "高等数学",
    mode: "review",
    mode_label: "考前复习",
    materials: [],
  });
  mock.onGet("/courses/math/interactive-classroom/s1/composition", {
    classroom_id: "room_ok",
    scene_total: 2,
    scenes: [{ type: "slide", count: 2 }],
  });

  const plan = await apiModule.getInteractiveClassroomPlan("math", "review");
  assert.equal(plan.mode, "review");
  assert.equal(plan.course_name, "高等数学");

  const composition = await apiModule.getInteractiveClassroomComposition("math", "s1");
  assert.equal(composition.scene_total, 2);
});

test("生成请求只发送学生真正填写的简报字段", async () => {
  const mock = createMockClient(apiModule.default);
  mock.reset();
  mock.onPost("/courses/math/interactive-classroom/generate", {
    session: { session_id: "s1", status: "queued" },
  });
  await apiModule.generateInteractiveClassroom("math", {
    mode: "quiz",
    learning_objective: "练熟矩阵乘法",
    desired_duration_minutes: 20,
    difficulty_level: "advanced",
    wants_more_practice: true,
    selected_material_ids: ["m1"],
  });
  const sent = mock.lastRequest();
  assert.equal(sent.method, "post");
  const body = sent.data;
  assert.equal(body.mode, "quiz");
  assert.equal(body.learning_objective, "练熟矩阵乘法");
  assert.equal(body.desired_duration_minutes, 20);
  assert.equal(body.difficulty_level, "advanced");
  assert.equal(body.wants_more_practice, true);
  assert.deepEqual(body.selected_material_ids, ["m1"]);
  // 未填写的字段不得出现在请求体里
  assert.equal("current_difficulty" in body, false);
});
