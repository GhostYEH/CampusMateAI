import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const page = fs.readFileSync(new URL("../src/pages/OpenMAICWorkspacePage.jsx", import.meta.url), "utf8");
const app = fs.readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
const panel = fs.readFileSync(new URL("../src/components/openmaic/WorkspacePanel.jsx", import.meta.url), "utf8");
const player = fs.readFileSync(new URL("../src/components/openmaic/StagePlayerPanel.jsx", import.meta.url), "utf8");
const quizRuntime = fs.readFileSync(new URL("../src/components/openmaic/QuizRuntimePanel.jsx", import.meta.url), "utf8");
const styles = fs.readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");

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
  assert.match(page, /window\.setTimeout\(\(\) => URL\.revokeObjectURL\(url\), 1000\)/);
  assert.match(panel, /window\.setTimeout\(\(\) => URL\.revokeObjectURL\(url\), 1000\)/);
  assert.match(page, /ProviderToolsPanel/);
  assert.match(page, /already populated workspace/);
  assert.match(page, /launchPrompt/);
});

test("workspace list links to the native workspace route", () => {
  assert.match(panel, /\/courses\/\$\{courseId\}\/workspaces\/\$\{item\.id\}/);
});

test("native quiz playback exposes the full answer and review runtime", () => {
  assert.match(player, /QuizRuntimePanel/);
  assert.match(quizRuntime, /开始答题/);
  assert.match(quizRuntime, /提交答案/);
  assert.match(quizRuntime, /答案解析/);
  assert.match(quizRuntime, /重新作答/);
});

test("workspace player has dedicated experiment and PBL runtime surfaces", () => {
  assert.match(player, /SimulationRuntimePanel/);
  assert.match(player, /PblRuntimePanel/);
  assert.match(styles, /openmaic-simulation-runtime/);
  assert.match(styles, /openmaic-pbl-runtime/);
});
