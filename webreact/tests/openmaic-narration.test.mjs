/**
 * 讲解音频视图模型与场景归属的契约测试。
 *
 * 这条链路最容易退化的是三件事，所以直接钉住它们：
 *
 * 1. **失败不能被说成"没有内容"。** 两者下一步动作不同（重试 vs 不必再点）；
 * 2. **音频必须按 scene id 绑定。** 换场景/刷新后 A 页的音频不能出现在 B 页；
 * 3. **Provider 未配置要说成部署问题**，不能伪装成网络抖动让人反复重试。
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { canGenerateNarration, describeNarrationFailure, narrationLabel } from "../src/features/openmaic/narrationModel.js";

const here = dirname(fileURLToPath(import.meta.url));
const read = (rel) => readFileSync(resolve(here, "..", rel), "utf8");

test("a scene with no script is not reported as a failure", () => {
  // "这一页没有可讲解的文字"不是错误：不该给一个可点的重试按钮去诱导学生重复操作。
  assert.equal(canGenerateNarration({ state: "none" }), false);
  assert.equal(narrationLabel({ state: "none" }), "这一页没有可讲解的文字。");
  // 失败才可重试。
  assert.equal(canGenerateNarration({ state: "error" }), true);
  assert.notEqual(narrationLabel({ state: "error" }), narrationLabel({ state: "none" }));
});

test("a scene with a script but no audio exposes the generate action", () => {
  assert.equal(canGenerateNarration({ state: "available" }), true);
  assert.match(narrationLabel({ state: "available" }), /生成讲解/);
  assert.equal(canGenerateNarration({ state: "none" }), false);
});

test("an in-flight generation cannot be started again from the UI", () => {
  assert.equal(canGenerateNarration({ state: "generating" }), false);
  assert.equal(canGenerateNarration({ state: "ready" }), false, "已经有音频就不该再出现生成入口");
  assert.equal(canGenerateNarration({ state: "checking" }), false);
});

test("every state has its own copy so nothing renders as a blank panel", () => {
  for (const state of ["checking", "generating", "ready", "available", "none", "error"]) {
    assert.ok(narrationLabel({ state }).length > 0, `${state} 必须有文案`);
  }
  assert.match(narrationLabel({ state: "ready", truncated: true }), /截断/);
});

test("the narration hook keeps a script-bearing scene actionable before its first job", () => {
  const hook = read("src/features/openmaic/useSceneNarration.js");
  assert.match(hook, /status\?\.has_script !== false/);
  assert.match(hook, /setState\(scriptAvailable \? "available" : "none"\)/);
});

test("failure copy distinguishes an unconfigured provider from a transient fault", () => {
  // 未配置是部署问题，重试无用 —— 必须与"网络抖动"给出不同的说法。
  const unconfigured = describeNarrationFailure({ code: "provider_unavailable" });
  const transient = describeNarrationFailure({ code: "provider_timeout" });
  assert.notEqual(unconfigured, transient);
  assert.match(unconfigured, /没有配置/);
  assert.match(transient, /再试一次/);

  assert.match(describeNarrationFailure({ response: { status: 503 } }), /没有配置/);
  assert.match(describeNarrationFailure({ response: { status: 404 } }), /不存在/);
  assert.match(describeNarrationFailure({ response: { status: 403 } }), /权限/);
});

test("an unknown failure still says something specific rather than swallowing it", () => {
  const withDetail = describeNarrationFailure({ response: { status: 500, data: { detail: "上游炸了" } } });
  assert.match(withDetail, /上游炸了/);
  assert.ok(describeNarrationFailure(new Error("boom")).includes("boom"));
  assert.ok(describeNarrationFailure(undefined).length > 0, "完全未知也要有兜底文案");
});

// ===== 场景归属：靠源码结构钉住，避免以后被"优化"掉 =====

test("narration is fetched per scene id, never from a shared or last-used slot", () => {
  const api = read("src/data/api.js");
  const hook = read("src/features/openmaic/useSceneNarration.js");

  // 每个请求都必须带上场景标识；少一个就会退化成"最近一页"。
  assert.match(api, /scenes\/\$\{sceneId\}\/narration/);
  assert.match(api, /scene_id:\s*sceneId/);
  // 读取与生成都走同一个按场景的端点。
  assert.match(hook, /getOpenMAICSceneNarration\(courseId, workspaceId, stageId, sceneId\)/);
  assert.match(hook, /synthesizeOpenMAICSceneNarration\(courseId, workspaceId, stageId, sceneId/);
  // 换场景时必须释放上一页的 blob URL，否则旧音频在新页仍可播放。
  assert.match(hook, /revokeObjectURL/, "必须在换场景/卸载时释放对象 URL");
  // 迟到的响应不得写进新上下文。
  assert.match(hook, /epoch/, "必须有代次守卫");
});

test("the classroom stage binds narration to the current scene, not to a fixed one", () => {
  const source = read("src/components/openmaic/OpenMAICClassroomStage.jsx");
  assert.match(
    source,
    /useSceneNarration\(\{\s*courseId,\s*workspaceId,\s*stageId,\s*sceneId:\s*currentId\s*\}\)/,
    "讲解必须绑定当前场景 currentId",
  );
  // 音频元素只在 ready 时挂载，切页后随组件消失 → 不可能串页。
  assert.match(source, /narration\.ready && audioUrl/);
});

test("the browser never sends narration text, only scene identifiers", () => {
  const api = read("src/data/api.js");
  const start = api.indexOf("export async function synthesizeOpenMAICSceneNarration");
  assert.ok(start > 0, "讲解生成函数必须存在");
  const body = api.slice(start, start + 700);
  // 请求体只允许标识符：带上 text 就等于让浏览器决定读什么，音频会与页面对不上。
  assert.match(body, /scene_id:\s*sceneId/);
  assert.doesNotMatch(body, /\btext\s*:/, "讲解请求不得携带自由文本");
});

test("the tts artifact is a real audio element so the browser owns playback", () => {
  const source = read("src/components/openmaic/OpenMAICClassroomStage.jsx");
  assert.match(source, /<audio/, "必须用真实 audio 元素播放，而不是自绘一个假控件");
  assert.match(source, /controls/);
});
