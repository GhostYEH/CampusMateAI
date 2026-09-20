import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

const read = (relative) => readFileSync(
  fileURLToPath(new URL(`../${relative}`, import.meta.url)),
  "utf8",
);

const editorSource = read("src/components/openmaic/StageEditorPanel.jsx");
const canvasSource = read("src/maic/edit/StageCanvasPreview.jsx");

test("the workbench editor reads a full stage document for its selected canvas", () => {
  assert.match(editorSource, /api\.getOpenMAICStage\(courseId, workspaceId, stageId\)/);
  assert.doesNotMatch(editorSource, /api\.getOpenMAICStageOutline\(/,
    "目录与画布必须从同一次完整 stage 读取，不能把不同 revision 拼在一起");
  assert.match(editorSource, /StageCanvasPreview/);
  assert.match(editorSource, /selectedSceneId/);
  assert.match(canvasSource, /data-scene-id/);
});

test("loading a full stage keeps action definitions instead of replacing them with outline counts", () => {
  assert.doesNotMatch(
    editorSource,
    /actions:\s*detailById\.get\(scene\.id\)\?\.actions/,
    "完整 DSL 的 actions 数组是播放时间线和后续编辑的事实源，不能被目录摘要覆盖",
  );
  assert.match(editorSource, /Array\.isArray\(scene\.actions\)/);
});

test("the editor preview reuses the playback slide surface", () => {
  assert.match(canvasSource, /<MaicSlideSurface canvas=\{canvas\}/);
  assert.match(canvasSource, /data-maic-edit-canvas="true"/);
  assert.match(canvasSource, /flex flex-col h-full/);
});
