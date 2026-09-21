import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const previewSource = fs.readFileSync(new URL("../src/pages/magicclassGenerationPreviewPage.jsx", import.meta.url), "utf8");
const appSource = fs.readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");

test("generation preview is a real route and does not jump to counselor", () => {
  assert.match(appSource, /path="\/courses\/:courseId\/magicclass-preview"/);
  assert.match(previewSource, /确认并生成课堂/);
  assert.match(previewSource, /api\.listMagicClassWorkspaces\(courseId/);
  assert.match(previewSource, /api\.createMagicClassWorkspace\(courseId/);
  assert.match(previewSource, /workspaceHref\(courseId, workspace\.id/);
  assert.doesNotMatch(previewSource, /counselor/i);
});

test("preview preserves the G-project flow requirements", () => {
  assert.match(previewSource, /可播放、可编辑并导出 PPTX/);
  assert.match(previewSource, /支持后续语音讲解/);
  assert.match(previewSource, /magicclassAttachment/);
  assert.match(previewSource, /magicclassWebSearch/);
});
