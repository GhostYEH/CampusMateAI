import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const testsDir = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(testsDir, "..");
const e2e = fs.readFileSync(path.join(testsDir, "e2e", "learner-state-closed-loop.py"), "utf8");
const learningStatePage = fs.readFileSync(path.join(webRoot, "src", "pages", "LearningStatePage.jsx"), "utf8");
const packageJson = JSON.parse(fs.readFileSync(path.join(webRoot, "package.json"), "utf8"));

test("learner-state E2E uses current generic contracts", () => {
  assert.doesNotMatch(e2e, /learner-state\/knowledge/);
  assert.doesNotMatch(e2e, /PRACTICE|受控练习/);
  assert.doesNotMatch(e2e, /pred-course-select|掌握度预测|表现预测|学习速度|预测评测/);
  assert.match(e2e, /projection_kind=WORLD|projection_kind.*WORLD/);
  assert.match(e2e, /model-transparency/);
  assert.match(e2e, /createSimulation|simulations/);
});

test("LearningStatePage does not expose the retired practice source label", () => {
  assert.doesNotMatch(learningStatePage, /PRACTICE\s*:/);
  assert.doesNotMatch(learningStatePage, /受控练习/);
});

test("learner-state E2E has an explicit package entry", () => {
  assert.equal(packageJson.scripts["test:e2e:learner-state"], "python tests/e2e/learner-state-closed-loop.py");
  assert.match(packageJson.scripts["test:all"], /test:e2e:learner-state/);
});
