/**
 * 「快速询问」的行为契约。
 *
 * 这里钉住的是导致真实故障的那条链：受管服务不可用时，一次课程页的提问**不能**
 * 变成整页 503。因此三类断言缺一不可：
 *
 * 1. 决策：能力没上报就不发那次必然失败的 `GET /workspaces`；
 * 2. 文案：503 的稳定 reason 决定说什么、能不能重试，绝不透出 Axios 英文；
 * 3. 隔离：失败只写输入区旁边的局部错误，不写页级 error。
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  generationPreviewHref,
  workspaceHref,
  describeQuickAskFailure,
  pickReusableWorkspace,
  quickAskRejection,
  shouldBindWorkspace,
} from "../src/features/magicclass/quickAskModel.js";
import { enterClassroomHref } from "../src/features/magicclass/enterClassroomModel.js";
import { DEFAULT_SELECTED_ROLE_IDS, MAGICCLASS_AGENT_ROLES } from "../src/features/magicclass/roleModel.js";
import { describeFusionState } from "../src/features/magicclass/homeModel.js";
import { describeWorkspaceError } from "../src/features/magicclass/workspaceModel.js";

const read = (rel) => readFileSync(new URL(`../${rel}`, import.meta.url), "utf8");
const pageSource = read("src/pages/ParityPages.jsx");
const homeSource = read("src/components/magicclass/magicclassHome.jsx");

// ===== 深链 =====

test("the magic class deep link carries the course, prompt, mode and roles", () => {
  const href = workspaceHref("crs_1", "ws_1", "什么是进程？", {
    mode: "preset",
    selectedRoleIds: DEFAULT_SELECTED_ROLE_IDS,
  });
  assert.match(href, /^\/courses\/crs_1\/workspaces\/ws_1\?/);
  assert.match(href, /\/courses\/crs_1\/workspaces\/ws_1/);
  assert.match(href, /prompt=%E4%BB%80%E4%B9%88%E6%98%AF%E8%BF%9B%E7%A8%8B%EF%BC%9F/);
  assert.match(href, /mode=preset/);
  assert.match(href, /roles=default-1%2Cdefault-3%2Cdefault-4/);
});

test("the classroom deep link carries only the course, and quick ask keeps the preview", () => {
  // 「进入课堂」直达只带课程：角色、模式、提示词都不由它提供。
  const href = enterClassroomHref("crs_1");
  assert.equal(href, "/courses/crs_1/classroom");
  assert.doesNotMatch(href, /magicclass-preview/);
  // 快速提问仍然走生成预览，并把用户输入完整带过去。
  assert.equal(
    generationPreviewHref("crs_1", "讲解进程和线程", { mode: "preset", selectedRoleIds: DEFAULT_SELECTED_ROLE_IDS, webSearch: true }),
    "/courses/crs_1/magicclass-preview?prompt=%E8%AE%B2%E8%A7%A3%E8%BF%9B%E7%A8%8B%E5%92%8C%E7%BA%BF%E7%A8%8B&mode=preset&roles=default-1%2Cdefault-3%2Cdefault-4&web=1",
  );
});

test("the deep link refuses to invent a workspace", () => {
  assert.throws(() => workspaceHref("crs_1", "", "q"), /工作台/);
  assert.match(workspaceHref("crs_1", "ws_9", "q"), /\/courses\/crs_1\/workspaces\/ws_9/);
});

test("a direct entry produces a clean workspace URL with no empty choice parameters", () => {
  // 直达入口没有用户选择，地址里就不该出现 prompt=/mode= 这类空参数：
  // 它们不代表任何真实决定，还会让同一个工作台产生多个不同 URL。
  const href = workspaceHref("crs_1", "ws_1", "");
  assert.equal(href, "/courses/crs_1/workspaces/ws_1");
  assert.doesNotMatch(href, /\?/, "没有可选参数时不应出现问号");
  assert.doesNotMatch(href, /mode=/);
  assert.doesNotMatch(href, /prompt=/);
  // 带真实主题时仍然带上。
  assert.match(workspaceHref("crs_1", "ws_1", "讲解进程"), /prompt=%E8%AE%B2%E8%A7%A3%E8%BF%9B%E7%A8%8B/);
});

test("the migrated role roster matches the reference classroom controls", () => {
  assert.deepEqual(MAGICCLASS_AGENT_ROLES.map((role) => role.name), [
    "AI教师", "AI助教", "显眼包", "好奇宝宝", "笔记员", "思考者",
  ]);
  assert.deepEqual(DEFAULT_SELECTED_ROLE_IDS, ["default-1", "default-3", "default-4"]);
  assert.equal(MAGICCLASS_AGENT_ROLES.find((role) => role.id === "default-1").required, true);
});

// ===== 决策 =====

test("a workspace is bound only when the server advertises workspace and generation", () => {
  assert.equal(shouldBindWorkspace(describeFusionState({ state: "ready", capabilities: ["workspace", "generation"] })), true);
  assert.equal(shouldBindWorkspace(describeFusionState({ state: "ready", capabilities: ["workspace"] })), false);
  assert.equal(shouldBindWorkspace(describeFusionState({ state: "ready", capabilities: ["folder"] })), false);

  for (const state of ["disabled", "unavailable", "degraded"]) {
    const view = describeFusionState({ state, capabilities: ["workspace"] });
    assert.equal(shouldBindWorkspace(view), false, `${state} 不能去绑定工作台`);
  }
  assert.equal(shouldBindWorkspace(null), false, "状态取不到时按不可用处理");
});

test("reusing a workspace takes the first real row and tolerates a bad payload", () => {
  assert.deepEqual(pickReusableWorkspace({ items: [{ id: "ws_1", name: "复习" }] }), { id: "ws_1", name: "复习" });
  assert.deepEqual(pickReusableWorkspace({ items: [null, { id: "" }, { id: "ws_2" }] }), { id: "ws_2", name: "" });
  assert.equal(pickReusableWorkspace({ items: [] }), null);
  assert.equal(pickReusableWorkspace(null), null);
});

// ===== 文案与可重试性 =====

test("the fusion switch being off is permanent, not something to retry", () => {
  const described = describeQuickAskFailure({
    response: { status: 503, data: { code: "MAGICCLASS_FUSION_UNAVAILABLE", message: "受管 magic class 服务未启用", details: { reason: "fusion_disabled" } } },
  });
  assert.equal(described.kind, "unavailable");
  assert.equal(described.retryable, false, "没启用时重试没有意义");
  assert.match(described.message, /未启用/);
  assert.ok(described.fallbackLabel, "必须留一条不依赖工作台的路");
});

test("an unreachable service stays retryable", () => {
  const described = describeQuickAskFailure({
    response: { status: 503, data: { code: "MAGICCLASS_FUSION_UNAVAILABLE", details: { reason: "service_unreachable" } } },
  });
  assert.equal(described.retryable, true);
  assert.match(described.message, /稍后重试/);
});

test("a missing secret or a rejected assertion is explained, not blamed on the user", () => {
  const unconfigured = describeQuickAskFailure({
    response: { status: 503, data: { code: "MAGICCLASS_FUSION_UNAVAILABLE", details: { reason: "service_unconfigured" } } },
  });
  assert.equal(unconfigured.retryable, false);
  assert.match(unconfigured.message, /管理员/);

  const rejected = describeQuickAskFailure({
    response: { status: 503, data: { code: "MAGICCLASS_FUSION_UNAVAILABLE", details: { reason: "assertion_rejected" } } },
  });
  assert.equal(rejected.retryable, false);
  assert.match(rejected.message, /管理员/);
});

test("a 503 without a reason keeps the older, retryable reading", () => {
  const described = describeWorkspaceError({
    response: { status: 503, data: { code: "MAGICCLASS_FUSION_UNAVAILABLE" } },
  });
  assert.equal(described.retryable, true);
  assert.equal(described.reason, "unknown");
});

test("no axios english ever reaches the user", () => {
  const timeout = describeQuickAskFailure({ code: "ECONNABORTED", message: "timeout of 8000ms exceeded" });
  assert.equal(timeout.message, "请求超时，请稍后重试");

  const offline = describeQuickAskFailure({ request: {}, message: "Network Error" });
  assert.match(offline.message, /无法连接到服务/);

  for (const error of [
    { response: { status: 503, data: { code: "MAGICCLASS_FUSION_UNAVAILABLE" } } },
    { response: { status: 409, data: { code: "MAGICCLASS_REVISION_CONFLICT" } } },
    { response: { status: 500, data: {} } },
    {},
  ]) {
    assert.doesNotMatch(describeQuickAskFailure(error).message, /Request failed with status code/i);
  }
});

test("a conflict is not retried as-is, and the fallback is always offered", () => {
  const described = describeQuickAskFailure({
    response: { status: 409, data: { code: "MAGICCLASS_IDEMPOTENCY_CONFLICT" } },
  });
  assert.equal(described.kind, "idempotency");
  assert.equal(described.retryable, false);
  assert.ok(described.fallbackLabel);
});

// ===== 提交前校验 =====

test("submission is refused with a reason instead of a dead button", () => {
  assert.equal(quickAskRejection({ query: "问题", courseId: "crs_1", busy: false }), null);
  assert.match(quickAskRejection({ query: "  ", courseId: "crs_1" }), /请输入/);
  assert.match(quickAskRejection({ query: "问题", courseId: "" }), /选择一门课程/);
  assert.match(quickAskRejection({ query: "问题", courseId: "crs_1", busy: true }), /正在处理/);
});

// ===== 源码契约：错误隔离与品牌 =====

test("the course surface uses direct classroom entry instead of the legacy quick-ask UI", () => {
  assert.doesNotMatch(pageSource, /onQuickAsk=/);
  assert.doesNotMatch(pageSource, /generationPreviewHref/);
  assert.match(homeSource, /api\.generateMagicClassHome/);
  assert.match(homeSource, /进入课堂/);
});

test("the home surface carries the magic class branding and classroom tagline", () => {
  assert.match(homeSource, /magicclass-reference__brand/);
  assert.match(homeSource, /<strong>\{"magic class"\}<\/strong>/);
  assert.match(homeSource, /Generative Learning in Multi-Agent Interactive Classroom/);
  assert.doesNotMatch(pageSource, /MagicClass \/ Courses/);
});

test("the classroom entry is keyboard reachable and names its course selector", () => {
  assert.match(homeSource, /aria-label="选择课程"/);
  assert.match(homeSource, /magicclass-reference-submit/);
  assert.match(homeSource, /role="status"/);
});

test("secondary tools expose their unavailable capabilities clearly", () => {
  assert.match(homeSource, /magicclass-reference-tools/);
  assert.match(homeSource, /title="附件能力尚未接通"/);
  assert.match(homeSource, /title="联网搜索能力尚未接通"/);
});

test("the home never renders a placeholder entry or an iframe", () => {
  assert.doesNotMatch(homeSource, /正在接入/);
  assert.doesNotMatch(homeSource, /TODO/);
  assert.doesNotMatch(homeSource, /iframe/);
});
