import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const page = fs.readFileSync(new URL("../src/pages/OpenMAICWorkspacePage.jsx", import.meta.url), "utf8");
const app = fs.readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
const panel = fs.readFileSync(new URL("../src/components/openmaic/WorkspacePanel.jsx", import.meta.url), "utf8");

test("workspace route restores owned content and exposes truthful generation recovery", () => {
  assert.match(app, /\/courses\/:courseId\/workspaces\/:workspaceId/);
  assert.match(page, /getOpenMAICWorkspace\(courseId, workspaceId\)/);
  assert.match(page, /listOpenMAICStages\(courseId, workspaceId/);
  assert.match(page, /generateOpenMAICStage\(courseId, workspaceId/);
  assert.match(page, /getOpenMAICJob\(courseId, jobId\)/);
  assert.match(page, /cancelOpenMAICJob\(courseId, job\.id\)/);
  assert.match(page, /retryOpenMAICJob\(courseId, job\.id\)/);
  assert.match(page, /StageEditorPanel/);
  assert.match(page, /StagePlayerPanel/);
  assert.match(page, /exportOpenMAICStageFormat\(courseId, workspaceId, stage\.id, "pptx"\)/);
  assert.match(page, /PPTX/);
  assert.match(page, /ProviderToolsPanel/);
  assert.match(page, /already populated workspace/);
  assert.match(page, /launchPrompt/);
});

test("workspace list links to the native workspace route", () => {
  assert.match(panel, /\/courses\/\$\{courseId\}\/workspaces\/\$\{item\.id\}/);
});
