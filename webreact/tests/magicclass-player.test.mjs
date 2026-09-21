/**
 * 播放器的 Web 侧契约测试。
 *
 * 播放器最容易"看起来能用其实不安全或不诚实"：把不该进 iframe 的内容放进去，
 * 或者用一个空白框冒充"渲染中"。这里的测试因此集中在三件事上：沙箱只减不增、
 * 无法渲染要说清缺什么、进度来自服务端而不是本地猜测。
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// 必须先于 api.js 加载，给 localStorage / location 提供确定性实现。
import "./helpers/setup-globals.mjs";
import * as apiModule from "../src/data/api.js";
import { createMockClient } from "./helpers/mock-client.mjs";
import {
  PLAYER_SANDBOX,
  actionTimeline,
  degradeNotice,
  describePlaybackError,
  normalizePlayback,
  playerNavigation,
  sandboxPolicyFor,
} from "../src/features/magicclass/playerModel.js";

const read = (rel) => readFileSync(fileURLToPath(new URL(`../${rel}`, import.meta.url)), "utf8");
const playerSource = read("src/components/magicclass/StagePlayerPanel.jsx");
const editorSource = read("src/components/magicclass/StageEditorPanel.jsx");
const apiSource = read("src/data/api.js");

const scene = (overrides = {}) => ({
  id: "scn_1",
  type: "slide",
  title: "开场",
  order: 0,
  render: { kind: "native" },
  steps: [],
  dropped_actions: [],
  whiteboards: 0,
  multi_agent: false,
  ...overrides,
});

// ===== 沙箱策略 =====

test("the only sandbox the player applies is allow-scripts", () => {
  assert.equal(PLAYER_SANDBOX, "allow-scripts");
  assert.doesNotMatch(PLAYER_SANDBOX, /allow-same-origin/);
});

test("an iframe is allowed only for sandbox kinds the server really marked", () => {
  assert.equal(sandboxPolicyFor({ kind: "native" }).allowIframe, false);
  assert.equal(sandboxPolicyFor({ kind: "unsupported" }).allowIframe, false);
  assert.equal(sandboxPolicyFor(undefined).allowIframe, false);
  assert.equal(sandboxPolicyFor({ kind: "sandbox-html", sandbox: "allow-scripts" }).allowIframe, true);
  assert.equal(sandboxPolicyFor({ kind: "sandbox-url", sandbox: "allow-scripts" }).allowIframe, true);
});

test("a sandbox that gained allow-same-origin is refused, not applied", () => {
  const widened = sandboxPolicyFor({ kind: "sandbox-html", sandbox: "allow-scripts allow-same-origin" });
  assert.equal(widened.allowIframe, false, "前端不得放大服务端给出的沙箱权限");
  const empty = sandboxPolicyFor({ kind: "sandbox-html", sandbox: "" });
  assert.equal(empty.allowIframe, false);
});

test("the sandbox string is used verbatim and never rebuilt in the component", () => {
  assert.match(playerSource, /sandbox=\{policy\.sandbox\}/);
  // 组件里不得出现任何硬编码或拼接的沙箱串；真正的保证在 sandboxPolicyFor。
  assert.doesNotMatch(playerSource, /sandbox="[^"]*allow-same-origin/);
  assert.doesNotMatch(playerSource, /sandbox=\{[^}]*allow-same-origin/);
  assert.doesNotMatch(playerSource, /sandbox=\{[^}]*policy\.kind/);
});

// ===== 降级 =====

test("an unsupported scene says what is missing instead of rendering nothing", () => {
  assert.match(degradeNotice({ render: { reason: "widget_requires_external_cdn" } }), /3D/);
  assert.match(degradeNotice({ render: { reason: "scene_type_unsupported" } }), /渲染器/);
  assert.match(degradeNotice({ render: { reason: "interactive_payload_missing" } }), /没有可播放/);
  // 未知原因也要说清"是哪种未知"，不能退化成空话。
  assert.match(degradeNotice({ render: { reason: "future_reason" } }), /future_reason/);
  assert.match(degradeNotice(undefined), /无法播放/);
});

test("the component renders the degraded branch for unsupported scenes only", () => {
  assert.match(playerSource, /currentScene\.render\.kind === "unsupported"/);
  assert.match(playerSource, /\{degradeNotice\(currentScene\)\}/);
  assert.match(playerSource, /currentScene\.render\.kind === "native"/);
});

test("native playback renders real slide elements and whiteboard payloads", () => {
  assert.match(playerSource, /canvas\.elements/);
  assert.match(playerSource, /scene\.whiteboards/);
  assert.match(playerSource, /canvas\.title/);
});

// ===== 计划与导航 =====

test("the plan is normalised, sorted by order and keeps the server resume index", () => {
  const plan = normalizePlayback({
    stage_id: "stg_1",
    workspace_id: "ws_1",
    title: "第一课",
    revision: 4,
    dsl_version: "0.3.0",
    start_index: 2,
    scenes: [
      scene({ id: "scn_b", order: 1 }),
      scene({ id: "scn_c", order: 2 }),
      scene({ id: "scn_a", order: 0 }),
      null,
    ],
    degraded: [{ scene_id: "scn_c", reason: "scene_type_unsupported" }],
  });
  assert.deepEqual(plan.scenes.map((item) => item.id), ["scn_a", "scn_b", "scn_c"]);
  assert.equal(plan.startIndex, 2);
  assert.equal(plan.revision, 4);
  assert.equal(plan.scenes.length, 3, "缺 id 的条目被丢弃");
});

test("an out-of-range resume index is clamped instead of pointing at a missing scene", () => {
  const plan = normalizePlayback({ scenes: [scene()], start_index: 9 });
  assert.equal(plan.startIndex, 0);
  const negative = normalizePlayback({ scenes: [scene(), scene({ id: "scn_2", order: 1 })], start_index: -5 });
  assert.equal(negative.startIndex, 0);
});

test("navigation never leaves the scene list", () => {
  const scenes = [scene({ id: "a", order: 0 }), scene({ id: "b", order: 1 }), scene({ id: "c", order: 2 })];

  const first = playerNavigation(scenes, 0);
  assert.equal(first.hasPrev, false);
  assert.equal(first.hasNext, true);
  assert.equal(first.prevIndex, null);
  assert.equal(first.nextIndex, 1);

  const last = playerNavigation(scenes, 2);
  assert.equal(last.hasNext, false);
  assert.equal(last.nextIndex, null);
  assert.equal(last.progress, 1);

  // 越界索引被夹紧，不会指向不存在的场景。
  assert.equal(playerNavigation(scenes, 99).index, 2);
  assert.equal(playerNavigation(scenes, -3).index, 0);

  const empty = playerNavigation([], 0);
  assert.equal(empty.total, 0);
  assert.equal(empty.progress, 0, "没有场景时不能除零");
  assert.equal(empty.hasNext, false);
});

test("the action timeline separates blocking steps from fire-and-forget ones", () => {
  const timeline = actionTimeline(scene({
    steps: [
      { action_id: "a1", type: "spotlight", mode: "fire_and_forget" },
      { action_id: "a2", type: "speech", mode: "sync" },
    ],
  }));
  assert.deepEqual(timeline, [
    { actionId: "a1", type: "spotlight", blocking: false },
    { actionId: "a2", type: "speech", blocking: true },
  ]);
  assert.deepEqual(actionTimeline(undefined), []);
});

test("dropped actions are surfaced to the viewer rather than silently disappearing", () => {
  const plan = normalizePlayback({
    scenes: [scene({ dropped_actions: [{ action_id: "a1", type: "spotlight", reason: "action_requires_slide_scene" }] })],
  });
  assert.equal(plan.scenes[0].droppedActions.length, 1);
  assert.match(playerSource, /个动作在当前场景类型下不会执行/);
});

// ===== 错误语义 =====

test("playback failures are classified so the viewer knows what to do", () => {
  assert.equal(describePlaybackError({ response: { status: 503, data: { code: "MAGICCLASS_FUSION_UNAVAILABLE" } } }).kind, "unavailable");
  assert.equal(describePlaybackError({ response: { status: 404, data: { code: "MAGICCLASS_WORKSPACE_NOT_FOUND" } } }).kind, "notFound");
  assert.equal(describePlaybackError({ response: { status: 400, data: { code: "MAGICCLASS_INVALID_REQUEST" } } }).kind, "invalid");
  const unknown = describePlaybackError({ response: { status: 500, data: { message: "boom" } } });
  assert.equal(unknown.kind, "unknown");
  assert.equal(unknown.retryable, true);
});

// ===== 请求协议与组合契约 =====

test("the playback request carries the resume scene and omits it when absent", async () => {
  const mock = createMockClient(apiModule.default);
  mock.onGet("/courses/c1/workspaces/ws_1/stages/stg_1/playback", { scenes: [] });
  await apiModule.getMagicClassStagePlayback("c1", "ws_1", "stg_1", { sceneId: "scn_2" });
  assert.equal(mock.requests.at(-1).params.scene_id, "scn_2");

  await apiModule.getMagicClassStagePlayback("c1", "ws_1", "stg_1");
  assert.equal("scene_id" in mock.requests.at(-1).params, false);
});

test("the player is reachable from the scene list (not dead code)", () => {
  assert.match(editorSource, /StagePlayerPanel/);
  assert.match(editorSource, /startSceneId=\{playingSceneId\}/);
  assert.match(playerSource, /getMagicClassStagePlayback/);
  assert.match(playerSource, /getMagicClassStageScene/);
});

test("the player re-reads on scope change and drops late responses", () => {
  assert.match(playerSource, /epoch\.current \+= 1/);
  assert.match(playerSource, /if \(mine !== epoch\.current\) return;/);
});

test("the browser never talks to the managed service directly from the player", () => {
  for (const source of [playerSource, apiSource]) {
    assert.doesNotMatch(source, /magicclass\.internal/);
    assert.doesNotMatch(source, /MAGICCLASS_INTERNAL_SECRET|magicclass_service_url/i);
  }
  assert.match(apiSource, /stages\/\$\{stageId\}\/playback/);
});
