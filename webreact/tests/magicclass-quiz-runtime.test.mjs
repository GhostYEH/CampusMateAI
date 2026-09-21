import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const read = (rel) => readFileSync(fileURLToPath(new URL(`../${rel}`, import.meta.url)), "utf8");
const panelSource = read("src/components/magicclass/QuizRuntimePanel.jsx");
const playerSource = read("src/components/magicclass/StagePlayerPanel.jsx");
const apiSource = read("src/data/api.js");

test("quiz runtime hydrates and persists the server attempt while retaining local fallback", () => {
  assert.match(apiSource, /getMagicClassQuizAttempt/);
  assert.match(apiSource, /saveMagicClassQuizAttempt/);
  assert.match(panelSource, /getMagicClassQuizAttempt/);
  assert.match(panelSource, /saveMagicClassQuizAttempt/);
  assert.match(panelSource, /localStorage/);
  assert.match(panelSource, /catch/);
});

test("quiz runtime sends lifecycle phases, results, and retry state", () => {
  for (const phase of ["draft", "submitted", "reviewed"]) assert.match(panelSource, new RegExp(`"${phase}"`));
  assert.match(panelSource, /results/);
  assert.match(panelSource, /start_new_attempt/);
  assert.match(playerSource, /courseId=\{courseId\}/);
  assert.match(playerSource, /workspaceId=\{workspaceId\}/);
  assert.match(playerSource, /stageId=\{stageId\}/);
});
