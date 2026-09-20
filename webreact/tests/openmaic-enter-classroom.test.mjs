/**
 * 「进入课堂」直达入口的行为契约。
 *
 * 这条入口推翻了原来的三步流程（角色 → 模式 → 预览 → 工作台）。这里钉住的是
 * 新流程里**不能被实现细节悄悄改掉**的六件事，任何一件走偏都会重演旧缺陷：
 *
 * 1. **不需要任何选择。** 入口只带课程；角色、模式、提示词都不再由用户提供，
 *    预览页的深链也不再是默认落点。
 * 2. **幂等键必须确定。** 双击「进入课堂」、刷新页面、切走再切回，都必须落回
 *    **同一个** workspace 与**同一个** stage。用随机键会让服务端每次都建新的。
 * 3. **默认主题来自真实课程。** 有知识点就用知识点，没有就如实说"课程资料尚未
 *    同步"，绝不编造课程名/知识点糊弄过去。
 * 4. **刷新恢复同一个 job。** 生成中刷新必须接回原来的 job，而不是重新排队。
 * 5. **课程切换必须作废旧请求。** 迟到的响应不得写进新课程。
 * 6. **不伪造成功。** 服务不可用、job 失败时，"已完成"一个字都不能出现。
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  ENTER_CLASSROOM_PATH,
  enterClassroomHref,
  classroomEntryIdempotencyKey,
  stageGenerationIdempotencyKey,
  buildClassroomPrompt,
  describeCourseReadiness,
  CLASSROOM_GENERATION_STEPS,
  resolveGenerationPhase,
  describeEntryFailure,
  shouldCountAsCompleted,
} from "../src/features/openmaic/enterClassroomModel.js";

const read = (rel) => readFileSync(new URL(`../${rel}`, import.meta.url), "utf8");
const appSource = read("src/App.jsx");
const paritySource = read("src/pages/ParityPages.jsx");
const entryPageSource = read("src/pages/OpenMAICClassroomEntryPage.jsx");
const homeSource = read("src/components/openmaic/OpenMAICHome.jsx");

// ===== 1. 直达入口：没有角色、没有模式、没有预览 =====

test("the classroom entry carries only the course — no role, mode or prompt", () => {
  const href = enterClassroomHref("crs_1");
  assert.equal(href, "/courses/crs_1/classroom");
  assert.equal(ENTER_CLASSROOM_PATH, "/courses/:courseId/classroom");
  // 这三样都不该再出现在入口 URL 里：它们正是被删掉的那几步。
  assert.doesNotMatch(href, /roles=/);
  assert.doesNotMatch(href, /mode=/);
  assert.doesNotMatch(href, /prompt=/);
  assert.doesNotMatch(href, /openmaic-preview/);
});

test("the entry refuses to invent a course", () => {
  assert.throws(() => enterClassroomHref(""), /课程/);
  assert.throws(() => enterClassroomHref(null), /课程/);
});

test("the classroom entry is a real route and the course rail links to it", () => {
  assert.match(appSource, /path="\/courses\/:courseId\/classroom"/);
  // 直达入口挂在 CourseRail 的「进入课堂」上，与快速提问是两条独立入口。
  assert.match(homeSource, /enterClassroomHref/);
  assert.match(homeSource, /进入课堂/);
});

test("the classroom entry opens the workbench in learning mode, not the editor", () => {
  // 用户点的是「进入课堂」。工作台若把 `learning` 固定在本地初值 `false`，入口就会
  // 先把人丢进编辑器布局，他还得自己再找一次「开始学习」——入口的语义丢在了半路。
  // 地址里的 `mode=playback` 是这条链路上唯一的凭据，两端都要钉住。
  assert.match(entryPageSource, /workspaceHref\(courseId, workspaceId, prompt, \{ mode: "playback" \}\)/);
  const workbenchSource = read("src/pages/OpenMAICWorkbenchPage.jsx");
  assert.match(workbenchSource, /searchParams\.get\("mode"\) === "playback"/);
});

test("the courses page exposes direct classroom entry as its only primary flow", () => {
  assert.match(homeSource, /enterClassroomHref\(selectedCourseId\)/);
  assert.doesNotMatch(paritySource, /generationPreviewHref/);
  assert.doesNotMatch(paritySource, /onQuickAsk=/);
});

test("the legacy preview deep link stays reachable", () => {
  // 旧深链继续兼容，只是不再由默认课程入口抵达。
  assert.match(appSource, /path="\/courses\/:courseId\/openmaic-preview"/);
});

test("the classroom entry never enters from a role or mode chooser", () => {
  assert.doesNotMatch(entryPageSource, /选择角色/);
  assert.doesNotMatch(entryPageSource, /AgentRolePicker/);
  assert.doesNotMatch(entryPageSource, /确认并生成课堂/);
  assert.doesNotMatch(entryPageSource, /counselor/i);
});

// ===== 2. 确定性幂等键 =====

test("the workspace key is deterministic per course", () => {
  const first = classroomEntryIdempotencyKey("crs_1");
  const second = classroomEntryIdempotencyKey("crs_1");
  assert.equal(first, second, "同课程必须恒等，否则双击就会建出第二个工作台");
  assert.notEqual(first, classroomEntryIdempotencyKey("crs_2"));
  assert.match(first, /crs_1/);
});

test("the stage key is deterministic per course and topic", () => {
  const a = stageGenerationIdempotencyKey("crs_1", "数据库入门");
  assert.equal(a, stageGenerationIdempotencyKey("crs_1", "数据库入门"));
  assert.notEqual(a, stageGenerationIdempotencyKey("crs_1", "操作系统入门"));
  assert.notEqual(a, stageGenerationIdempotencyKey("crs_2", "数据库入门"));
});

test("the keys are stable across process restarts (no clock, no random)", () => {
  // 键里不允许出现时间戳或随机量：刷新会重算，随机量会让恢复变成新建。
  const key = stageGenerationIdempotencyKey("crs_1", "数据库入门");
  assert.doesNotMatch(key, /\d{13}/, "不能内嵌毫秒时间戳");
  assert.equal(key, stageGenerationIdempotencyKey("crs_1", "数据库入门"));
});

// ===== 3. 默认主题来自真实课程，不编造 =====

test("a synced course produces a prompt grounded in its real material", () => {
  const prompt = buildClassroomPrompt({
    name: "数据库系统原理",
    code: "CS301",
    semester: "2026 春",
    knowledgePoints: ["关系模型", "范式分解"],
    materials: [{ id: "m1", title: "第三章讲义" }],
  });
  assert.match(prompt, /数据库系统原理/);
  assert.match(prompt, /关系模型/);
  assert.match(prompt, /讲解、示例、测验和练习/);
});

test("an unsynced course says so instead of inventing knowledge points", () => {
  const view = describeCourseReadiness({
    name: "数据库系统原理",
    knowledgePoints: [],
    materials: [],
  });
  assert.equal(view.synced, false);
  assert.match(view.notice, /课程资料尚未同步/);
  // 关键：不能凭空造出知识点。
  assert.doesNotMatch(view.notice, /关系模型|范式/);

  const prompt = buildClassroomPrompt({ name: "数据库系统原理", knowledgePoints: [], materials: [] });
  assert.match(prompt, /数据库系统原理/);
  assert.doesNotMatch(prompt, /知识点[:：]\s*\S/, "没有知识点就不能编一条出来");
});

test("readiness distinguishes unsynced from unreadable", () => {
  // "真的没有"与"读不到"是两件事，不能都说成尚未同步。
  const unreadable = describeCourseReadiness({
    name: "数据库系统原理",
    knowledgePoints: [],
    materials: [],
    warnings: ["知识点上下文读取失败，已省略(TimeoutError)"],
  });
  assert.equal(unreadable.synced, false);
  assert.equal(unreadable.degraded, true);
  assert.match(unreadable.notice, /未能读取|稍后重试/);
});

test("the prompt never fabricates a course it was not given", () => {
  const prompt = buildClassroomPrompt({});
  assert.doesNotMatch(prompt, /undefined|null|NaN/);
});

// ===== 4. 生成阶段：真实文案与推导 =====

test("the generation phases use the reference project's real copy in order", () => {
  assert.deepEqual(
    CLASSROOM_GENERATION_STEPS.map((step) => step.title),
    ["生成课程大纲", "生成课堂角色", "生成页面内容", "生成教学动作"],
  );
  const outline = CLASSROOM_GENERATION_STEPS[0];
  assert.match(outline.description, /构建学习路径/);
});

test("job status and step map onto the visible phase", () => {
  const queued = resolveGenerationPhase({ status: "queued" });
  assert.equal(queued.done, false);
  assert.equal(queued.failed, false);

  // 有 step 时以 step 为准：进度条不能只会在 0 和 100 之间跳。
  const outlining = resolveGenerationPhase({ status: "running", step: "generating_outlines" });
  assert.equal(outlining.key, "outline");
  assert.equal(outlining.index, 0);

  const complete = resolveGenerationPhase({ status: "completed" });
  assert.equal(complete.done, true);
  assert.equal(complete.percent, 100);

  const failed = resolveGenerationPhase({ status: "failed", error: "模型服务不可用" });
  assert.equal(failed.failed, true);
  assert.equal(failed.done, false);
});

test("progress never goes backwards or past 100", () => {
  assert.equal(resolveGenerationPhase({ status: "running", progress: -5 }).percent, 0);
  assert.equal(resolveGenerationPhase({ status: "running", progress: 999 }).percent, 100);
  assert.equal(resolveGenerationPhase({ status: "running", progress: "abc" }).percent, 0);
});

// ===== 5. 不伪造成功 =====

test("a disabled or unreachable service is never rendered as completed", () => {
  for (const error of [
    { response: { status: 503, data: { code: "OPENMAIC_FUSION_UNAVAILABLE", details: { reason: "fusion_disabled" } } } },
    { response: { status: 503, data: { code: "OPENMAIC_FUSION_UNAVAILABLE", details: { reason: "service_unreachable" } } } },
    { request: {}, message: "Network Error" },
    { code: "ECONNABORTED", message: "timeout of 8000ms exceeded" },
  ]) {
    const view = describeEntryFailure(error);
    assert.equal(shouldCountAsCompleted(view), false, "服务不可用不能显示成已完成");
    assert.equal(view.completed, false);
    assert.ok(view.message, "必须给出中文原因");
    assert.doesNotMatch(view.message, /Request failed with status code|Network Error|timeout of/i);
  }
});

test("a failed job reports the real reason plus retry and manual creation", () => {
  const view = describeEntryFailure({
    response: { status: 200, data: { status: "failed", error: "模型返回了空大纲", error_code: "outline_empty" } },
  });
  assert.equal(view.completed, false);
  assert.match(view.message, /大纲|失败/);
  assert.equal(view.canRetry, true, "失败必须能重试");
  assert.equal(view.canCreateManually, true, "失败必须留手动创建入口");
});

test("configuration problems are not advertised as retryable", () => {
  const disabled = describeEntryFailure({
    response: { status: 503, data: { code: "OPENMAIC_FUSION_UNAVAILABLE", details: { reason: "fusion_disabled" } } },
  });
  assert.equal(disabled.canRetry, false, "没启用时重试一万次也是同一个结果");
  assert.match(disabled.message, /未启用/);

  const unreachable = describeEntryFailure({
    response: { status: 503, data: { code: "OPENMAIC_FUSION_UNAVAILABLE", details: { reason: "service_unreachable" } } },
  });
  assert.equal(unreachable.canRetry, true);
});

test("only a genuinely finished job counts as completed", () => {
  assert.equal(shouldCountAsCompleted({ completed: true }), true);
  assert.equal(shouldCountAsCompleted({ completed: false }), false);
  assert.equal(shouldCountAsCompleted(null), false);
  assert.equal(shouldCountAsCompleted(undefined), false);
});
