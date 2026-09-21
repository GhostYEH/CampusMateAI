/**
 * 编辑器的 Web 侧契约测试。
 *
 * 编辑器是唯一"客户端和服务端各持一份文档"的面，所以这里重点不是渲染，而是
 * 三条会造成真实损坏的规则：提交的是命令不是文档；undo/redo 有上限；本地不接受
 * 的命令绝不发出去（否则界面与服务端分叉）。
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
  EDITOR_HISTORY_LIMIT,
  MAX_COMMANDS_PER_REQUEST,
  SCENE_TYPES,
  applyCommandLocally,
  canSubmitCommands,
  createCommandBuffer,
  describeEditorError,
  normalizeOutline,
  sceneCreateCommand,
  sceneDeleteCommand,
  sceneDuplicateCommand,
  sceneMoveCommand,
  sceneUpdateCommand,
  slideElementMoveCommand,
  slideElementAddCommand,
  slideElementDeleteCommand,
  slideElementTransformCommand,
  slideElementUpdateCommand,
} from "../src/features/magicclass/editorModel.js";

const read = (rel) => readFileSync(fileURLToPath(new URL(`../${rel}`, import.meta.url)), "utf8");
const editorSource = read("src/components/magicclass/StageEditorPanel.jsx");
const workspaceSource = read("src/components/magicclass/WorkspacePanel.jsx");
const apiSource = read("src/data/api.js");

const documentWith = (scenes = []) => ({
  dslVersion: "0.3.0",
  stage: { id: "stg_1", name: "第一课", createdAt: 1, updatedAt: 1 },
  scenes,
});

// ===== 命令与本地镜像 =====

test("a scene.create mirrors the server's minimal content and keeps orders dense", () => {
  let document = documentWith();
  document = applyCommandLocally(document, { ...sceneCreateCommand("slide"), localId: "s1" });
  document = applyCommandLocally(document, { ...sceneCreateCommand("quiz"), localId: "s2" });
  assert.deepEqual(document.scenes.map((scene) => scene.order), [0, 1]);
  assert.deepEqual(document.scenes[0].content, { type: "slide", canvas: {} });
  assert.equal(document.scenes[1].content.type, "quiz");
});

test("an interactive scene is refused locally instead of being drawn and rejected later", () => {
  assert.throws(
    () => applyCommandLocally(documentWith(), sceneCreateCommand("interactive")),
    (error) => error.code === "interactive_content_required",
  );
});

test("a local update cannot change a scene's type", () => {
  const document = documentWith([
    { id: "s1", type: "slide", title: "开场", order: 0, content: { type: "slide", canvas: {} } },
  ]);
  assert.throws(
    () => applyCommandLocally(document, sceneUpdateCommand("s1", { content: { type: "quiz", questions: [] } })),
    (error) => error.code === "content_type_mismatch",
  );
});

test("a local move refuses an out-of-range target and reindexes on success", () => {
  const document = documentWith([
    { id: "s1", type: "slide", title: "A", order: 0, content: { type: "slide", canvas: {} } },
    { id: "s2", type: "quiz", title: "B", order: 1, content: { type: "quiz", questions: [] } },
  ]);
  assert.throws(() => applyCommandLocally(document, sceneMoveCommand("s1", 5)), (error) => error.code === "scene_move_out_of_range");
  const moved = applyCommandLocally(document, sceneMoveCommand("s2", 0));
  assert.deepEqual(moved.scenes.map((scene) => scene.id), ["s2", "s1"]);
  assert.deepEqual(moved.scenes.map((scene) => scene.order), [0, 1]);
});

test("slide.element.move mirrors only a finite coordinate pair on an existing slide element", () => {
  const document = documentWith([{
    id: "s1", type: "slide", title: "A", order: 0,
    actions: [{ id: "a1", type: "speech", text: "保留" }],
    content: {
      type: "slide",
      canvas: { elements: [{ id: "e1", type: "text", left: 10, top: 20, width: 100, height: 40 }] },
    },
  }]);
  const command = slideElementMoveCommand("s1", "e1", 120.5, 80.25);
  const moved = applyCommandLocally(document, command);
  assert.deepEqual(moved.scenes[0].content.canvas.elements[0], {
    id: "e1", type: "text", left: 120.5, top: 80.25, width: 100, height: 40,
  });
  assert.deepEqual(moved.scenes[0].actions, document.scenes[0].actions);
  assert.throws(() => slideElementMoveCommand("s1", "e1", Number.NaN, 1), (error) => error.code === "command_field_invalid");
  assert.throws(() => applyCommandLocally(document, slideElementMoveCommand("s1", "missing", 1, 1)), (error) => error.code === "element_not_found");
  assert.throws(() => applyCommandLocally({ ...document, scenes: [{ ...document.scenes[0], type: "quiz", content: { type: "quiz", questions: [] } }] }, slideElementMoveCommand("s1", "e1", 1, 1)), (error) => error.code === "slide_element_requires_slide");
  const missingPosition = documentWith([{
    id: "s2", type: "slide", title: "B", order: 0,
    content: { type: "slide", canvas: { elements: [{ id: "e2", type: "shape" }] } },
  }]);
  assert.throws(
    () => applyCommandLocally(missingPosition, slideElementMoveCommand("s2", "e2", 1, 1)),
    (error) => error.code === "element_position_invalid" && error.path === "elementId",
  );
  const nonFinitePosition = documentWith([{
    id: "s3", type: "slide", title: "C", order: 0,
    content: { type: "slide", canvas: { elements: [{ id: "e3", type: "shape", left: 0, top: Number.POSITIVE_INFINITY }] } },
  }]);
  assert.throws(
    () => applyCommandLocally(nonFinitePosition, slideElementMoveCommand("s3", "e3", 1, 1)),
    (error) => error.code === "element_position_invalid" && error.path === "elementId",
  );
});

test("slide.element.transform mirrors all finite geometry fields on an existing slide element", () => {
  const document = documentWith([{
    id: "s1", type: "slide", title: "A", order: 0,
    content: { type: "slide", canvas: { elements: [
      { id: "e1", type: "shape", left: 10, top: 20, width: 100, height: 40, rotate: 0 },
    ] } },
  }]);
  const command = slideElementTransformCommand("s1", "e1", {
    left: 30, top: 40, width: 120, height: 60, rotate: 15,
  });
  assert.deepEqual(command, {
    type: "slide.element.transform", sceneId: "s1", elementId: "e1",
    left: 30, top: 40, width: 120, height: 60, rotate: 15,
  });
  const transformed = applyCommandLocally(document, command);
  assert.deepEqual(transformed.scenes[0].content.canvas.elements[0], {
    id: "e1", type: "shape", left: 30, top: 40, width: 120, height: 60, rotate: 15,
  });
  assert.throws(() => slideElementTransformCommand("s1", "e1", {
    left: 30, top: 40, width: 0, height: 60, rotate: 15,
  }), (error) => error.code === "command_field_invalid");
});

test("slide.element.transform accepts a bounded partial patch and initializes legacy rotation", () => {
  const command = slideElementTransformCommand("s1", "e1", { rotate: 30 });
  assert.deepEqual(command, { type: "slide.element.transform", sceneId: "s1", elementId: "e1", rotate: 30 });
  const document = documentWith([{
    id: "s1", type: "slide", title: "A", order: 0,
    content: { type: "slide", canvas: { elements: [{ id: "e1", type: "text", left: 1, top: 2, width: 3, height: 4 }] } },
  }]);
  assert.equal(applyCommandLocally(document, command).scenes[0].content.canvas.elements[0].rotate, 30);
  assert.throws(() => slideElementTransformCommand("s1", "e1", {}), (error) => error.code === "command_no_effect");
});

test("slide.element.add and delete mirror the service element payload contract", () => {
  const document = documentWith([{
    id: "s1", type: "slide", title: "A", order: 0,
    actions: [{ id: "a1" }],
    content: { type: "slide", canvas: {
      elements: [{ id: "e1", type: "shape", left: 10, top: 20, width: 100, height: 40, rotate: 0 }],
      animations: [{ id: "anim", elId: "e1" }],
    } },
  }]);
  const element = { id: "e2", type: "text", left: 30, top: 40, width: 160, height: 52, rotate: 0, content: "<p>新增文本</p>" };
  const added = applyCommandLocally(document, slideElementAddCommand("s1", element, 0));
  assert.deepEqual(added.scenes[0].content.canvas.elements.map((entry) => entry.id), ["e2", "e1"]);
  assert.notEqual(added.scenes[0].content.canvas.elements[0], element);
  assert.deepEqual(added.scenes[0].actions, document.scenes[0].actions);
  const deleted = applyCommandLocally(added, slideElementDeleteCommand("s1", "e1"));
  assert.deepEqual(deleted.scenes[0].content.canvas.elements.map((entry) => entry.id), ["e2"]);
  assert.deepEqual(deleted.scenes[0].content.canvas.animations, []);
  assert.throws(() => slideElementAddCommand("s1", { ...element, width: 0 }), (error) => error.code === "element_geometry_invalid");
  assert.throws(() => applyCommandLocally(document, slideElementDeleteCommand("s1", "missing")), (error) => error.code === "element_not_found");
});

test("slide.element.update changes only an existing text element payload", () => {
  const document = documentWith([{
    id: "s1", type: "slide", title: "A", order: 0,
    actions: [{ id: "a1", type: "speech", text: "保留" }],
    content: { type: "slide", canvas: { elements: [
      { id: "e1", type: "text", content: "旧文本", left: 10, top: 20 },
      { id: "e2", type: "shape", left: 30, top: 40 },
    ] } },
  }]);
  const updated = applyCommandLocally(document, slideElementUpdateCommand("s1", "e1", "<p>新文本</p>"));
  assert.equal(updated.scenes[0].content.canvas.elements[0].content, "<p>新文本</p>");
  assert.equal(updated.scenes[0].content.canvas.elements[0].left, 10);
  assert.deepEqual(updated.scenes[0].actions, document.scenes[0].actions);
  assert.throws(() => applyCommandLocally(document, slideElementUpdateCommand("s1", "e2", "文本")), (error) => error.code === "element_type_invalid");
});

test("duplicating locally deep-copies the payload", () => {
  const document = documentWith([
    { id: "s1", type: "quiz", title: "A", order: 0, content: { type: "quiz", questions: [{ id: "q1" }] } },
  ]);
  const copied = applyCommandLocally(document, { ...sceneDuplicateCommand("s1"), localId: "s2" });
  assert.equal(copied.scenes.length, 2);
  assert.notEqual(copied.scenes[0].content, copied.scenes[1].content);
  assert.match(copied.scenes[1].title, /副本/);
});

test("every declared scene type is accepted by the command builder", () => {
  for (const type of SCENE_TYPES) {
    assert.equal(sceneCreateCommand(type).sceneType, type);
  }
  assert.throws(() => sceneCreateCommand("video"), (error) => error.code === "scene_type_invalid");
});

// ===== 命令缓冲：undo/redo 有界 =====

test("the buffer derives its preview from the server snapshot plus pending commands", () => {
  const buffer = createCommandBuffer();
  buffer.setBase(documentWith(), 3);
  assert.equal(buffer.preview().scenes.length, 0);
  buffer.run({ ...sceneCreateCommand("slide"), localId: "s1" });
  assert.equal(buffer.preview().scenes.length, 1);
  assert.equal(buffer.isDirty(), true);
  assert.equal(buffer.revision, 3);
});

test("a rejected command never enters the buffer", () => {
  const buffer = createCommandBuffer();
  buffer.setBase(documentWith(), 1);
  assert.throws(() => buffer.run(sceneCreateCommand("interactive")));
  assert.equal(buffer.pendingCount, 0, "本地不接受的命令不得留在缓冲里");
  assert.equal(buffer.isDirty(), false);
});

test("undo and redo walk the pending commands and redo is cleared by a new edit", () => {
  const buffer = createCommandBuffer();
  buffer.setBase(documentWith(), 1);
  buffer.run({ ...sceneCreateCommand("slide"), localId: "s1" });
  buffer.run({ ...sceneCreateCommand("quiz"), localId: "s2" });
  assert.equal(buffer.preview().scenes.length, 2);

  buffer.undo();
  assert.equal(buffer.preview().scenes.length, 1);
  buffer.undo();
  assert.equal(buffer.preview().scenes.length, 0);
  assert.equal(buffer.canUndo(), false);

  buffer.redo();
  assert.equal(buffer.preview().scenes.length, 1);

  buffer.run({ ...sceneCreateCommand("slide"), localId: "s3" });
  assert.equal(buffer.canRedo(), false, "新编辑必须清空 redo 分支");
});

test("the undo depth is bounded while unsaved edits are never dropped", () => {
  const buffer = createCommandBuffer({ limit: 5 });
  buffer.setBase(documentWith(), 1);
  for (let index = 0; index < 20; index += 1) {
    buffer.run({ ...sceneCreateCommand("slide"), localId: `s${index}` });
  }
  // 20 条编辑一条都不能丢 —— 丢用户的编辑比多占一点内存糟糕得多。
  assert.equal(buffer.pendingCount, 20);
  assert.equal(buffer.snapshot().length, 20);
  assert.equal(buffer.preview().scenes.length, 20);

  // 但撤销深度只有 5：再撤销时缓冲不再变化。
  let undoSteps = 0;
  while (buffer.canUndo()) {
    buffer.undo();
    undoSteps += 1;
  }
  assert.equal(undoSteps, 5);
  assert.equal(buffer.preview().scenes.length, 15);
});

test("too many unsaved edits are refused instead of silently discarding the oldest", () => {
  const buffer = createCommandBuffer({ pendingLimit: 3 });
  buffer.setBase(documentWith(), 1);
  buffer.run({ ...sceneCreateCommand("slide"), localId: "a" });
  buffer.run({ ...sceneCreateCommand("slide"), localId: "b" });
  buffer.run({ ...sceneCreateCommand("slide"), localId: "c" });
  assert.throws(
    () => buffer.run({ ...sceneCreateCommand("slide"), localId: "d" }),
    (error) => error.code === "pending_limit_reached",
  );
  assert.equal(buffer.pendingCount, 3, "拒绝后不得静默丢掉最早的一条");
});

test("saving splits pending commands at the server's per-request limit", () => {
  const buffer = createCommandBuffer({ limit: EDITOR_HISTORY_LIMIT });
  buffer.setBase(documentWith(), 1);
  for (let index = 0; index < MAX_COMMANDS_PER_REQUEST + 3; index += 1) {
    buffer.run({ ...sceneCreateCommand("slide"), localId: `s${index}` });
  }
  const batches = buffer.takeBatches();
  assert.equal(batches.length, 2);
  assert.equal(batches[0].length, MAX_COMMANDS_PER_REQUEST);
  assert.equal(batches[1].length, 3);
  assert.equal(canSubmitCommands(batches[0]), true);
  assert.equal(canSubmitCommands([]), false);
  assert.equal(canSubmitCommands(new Array(MAX_COMMANDS_PER_REQUEST + 1).fill({})), false);
});

test("resetting the base after a save clears the buffer so nothing is submitted twice", () => {
  const buffer = createCommandBuffer();
  buffer.setBase(documentWith(), 1);
  buffer.run({ ...sceneCreateCommand("slide"), localId: "s1" });
  buffer.setBase(documentWith([{ id: "srv_1", type: "slide", title: "新场景", order: 0 }]), 2);
  assert.equal(buffer.pendingCount, 0);
  assert.equal(buffer.isDirty(), false);
  assert.equal(buffer.revision, 2);
  assert.equal(buffer.preview().scenes.length, 1);
});

test("a conflict can update the revision without discarding the buffer", () => {
  const buffer = createCommandBuffer();
  buffer.setBase(documentWith(), 1);
  buffer.run({ ...sceneCreateCommand("slide"), localId: "s1" });
  buffer.setRevision(7);
  assert.equal(buffer.revision, 7);
  assert.equal(buffer.pendingCount, 1, "只更新 revision 不应丢掉未提交的命令");
});

// ===== 读模型与错误翻译 =====

test("the outline is sorted by order and unknown scene types are marked, not guessed", () => {
  const outline = normalizeOutline({
    stage_id: "stg_1",
    workspace_id: "ws_1",
    title: "第一课",
    revision: 4,
    dsl_version: "0.3.0",
    scenes: [
      { id: "s2", type: "quiz", title: "B", order: 1, actions: 0 },
      { id: "s1", type: "slide", title: "A", order: 0, actions: 2 },
      { id: "s3", type: "whiteboard", title: "未知", order: 2 },
      null,
    ],
  });
  assert.deepEqual(outline.scenes.map((scene) => scene.id), ["s1", "s2", "s3"]);
  assert.equal(outline.scenes[0].actions, 2);
  assert.equal(outline.scenes[2].type, "unsupported", "未知类型不得冒充成已知类型");
});

test("a rejected command surfaces the offending path", () => {
  const described = describeEditorError({
    response: {
      status: 422,
      data: {
        code: "MAGICCLASS_DOCUMENT_REJECTED",
        message: "这条编辑无法应用。",
        details: { service_error: "command_rejected", path: "commands[0].content" },
      },
    },
  });
  assert.equal(described.kind, "commandRejected");
  assert.equal(described.path, "commands[0].content");
});

test("a revision conflict is reported as a conflict, not as an unknown failure", () => {
  const described = describeEditorError({
    response: { status: 409, data: { code: "MAGICCLASS_REVISION_CONFLICT" } },
  });
  assert.equal(described.kind, "conflict");
  assert.equal(described.retryable, false);
});

test("idempotency, unavailable, notFound and invalid each keep their own kind", () => {
  const cases = [
    [{ response: { status: 409, data: { code: "MAGICCLASS_IDEMPOTENCY_CONFLICT" } } }, "idempotency"],
    [{ response: { status: 503, data: { code: "MAGICCLASS_FUSION_UNAVAILABLE" } } }, "unavailable"],
    [{ response: { status: 404, data: { code: "MAGICCLASS_WORKSPACE_NOT_FOUND" } } }, "notFound"],
    [{ response: { status: 400, data: { code: "MAGICCLASS_INVALID_REQUEST" } } }, "invalid"],
  ];
  for (const [error, kind] of cases) {
    assert.equal(describeEditorError(error).kind, kind);
  }
});

// ===== 请求协议与组合契约 =====

test("saving sends commands with If-Match and an Idempotency-Key, never a document", async () => {
  const mock = createMockClient(apiModule.default);
  mock.onPost("/courses/c1/workspaces/ws_1/stages/stg_1/commands", { id: "stg_1", revision: 2 });
  await apiModule.applyMagicClassStageCommands("c1", "ws_1", "stg_1", {
    commands: [sceneCreateCommand("slide")],
    revision: 1,
    idempotencyKey: "edit-1",
  });
  const call = mock.requests.at(-1);
  assert.equal(call.headers["If-Match"], "1");
  assert.equal(call.headers["Idempotency-Key"], "edit-1");
  assert.equal(Array.isArray(call.data.commands), true);
  assert.equal("document" in call.data, false, "编辑器不得整份回传文档");
});

test("editor exposes a bounded scene document editor backed by scene.update", () => {
  assert.match(editorSource, /api\.getMagicClassStageScene\(/);
  assert.match(editorSource, /aria-label="场景 DSL 内容"/);
  assert.match(editorSource, /sceneUpdateCommand\(.*content/s);
});

test("editor canvas exposes single selection, blank cancellation, and pointerup-only move wiring", () => {
  const canvasSource = read("src/maic/edit/StageCanvasPreview.jsx");
  assert.match(canvasSource, /data-maic-element-id/);
  assert.match(canvasSource, /onPointerDown/);
  assert.match(canvasSource, /setPointerCapture/);
  assert.match(canvasSource, /onMoveElement/);
  assert.match(canvasSource, /pointerup/);
  assert.doesNotMatch(canvasSource, /sceneElementDelete|multi/);
  assert.match(editorSource, /slideElementMoveCommand/);
  assert.match(editorSource, /onMoveElement/);
});

test("the outline and a single scene are read from the editor endpoints", async () => {
  const mock = createMockClient(apiModule.default);
  mock.onGet("/courses/c1/workspaces/ws_1/stages/stg_1/outline", { stage_id: "stg_1", scenes: [] });
  mock.onGet("/courses/c1/workspaces/ws_1/stages/stg_1/scenes/scn_1", { id: "scn_1" });
  await apiModule.getMagicClassStageOutline("c1", "ws_1", "stg_1");
  await apiModule.getMagicClassStageScene("c1", "ws_1", "stg_1", "scn_1");
  assert.equal(mock.requests[0].url, "/courses/c1/workspaces/ws_1/stages/stg_1/outline");
  assert.equal(mock.requests[1].url, "/courses/c1/workspaces/ws_1/stages/stg_1/scenes/scn_1");
});

test("the editor surface is reachable from the workspace panel (not dead code)", () => {
  assert.match(workspaceSource, /StageEditorPanel/);
  assert.match(workspaceSource, /listMagicClassStages/);
assert.match(editorSource, /applyMagicClassStageCommands/);
assert.match(editorSource, /slideElementUpdateCommand/);
assert.match(read("src\/maic\/edit\/StageCanvasPreview.jsx"), /ProseMirrorTextEditor/);
assert.match(read("src\/maic\/edit\/ProseMirrorTextEditor.jsx"), /EditorView/);
assert.match(read("src\/maic\/edit\/ProseMirrorTextEditor.jsx"), /onPointerDown/);
assert.doesNotMatch(read("src\/maic\/edit\/StageCanvasPreview.jsx"), /dangerouslySetInnerHTML/);
  assert.match(editorSource, /createCommandBuffer/);
});

test("the editor keeps the service's conflict and capability rules in the UI", () => {
  // 冲突后必须重新读取，而不是原样重放命令。
  assert.match(editorSource, /kind === "conflict"/);
  assert.match(editorSource, /await load\(\)/);
  // 离线时不得渲染可点击的编辑入口。
  assert.match(workspaceSource, /canEdit/);
  // 未上报 editor 能力时不加载编辑器。
  assert.match(workspaceSource, /canEdit \?/);
});

test("the browser never talks to the managed service directly from the editor", () => {
  for (const source of [editorSource, apiSource]) {
    assert.doesNotMatch(source, /magicclass\.internal/);
    assert.doesNotMatch(source, /MAGICCLASS_INTERNAL_SECRET|magicclass_service_url/i);
  }
  assert.match(apiSource, /stages\/\$\{stageId\}\/commands/);
  assert.match(apiSource, /stages\/\$\{stageId\}\/outline/);
});

test("the editor model exposes no unbounded history", () => {
  assert.equal(typeof EDITOR_HISTORY_LIMIT, "number");
  assert.ok(EDITOR_HISTORY_LIMIT > 0 && EDITOR_HISTORY_LIMIT <= 200);
  assert.match(read("src/features/magicclass/editorModel.js"), /while \(past\.length > limit\) past\.shift\(\);/);
});
