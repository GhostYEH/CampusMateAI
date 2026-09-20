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
  const entry = packageJson.scripts["test:e2e:learner-state"];
  // 裸 `python` 在 Windows 开发机上不成立（本机只有 backend/.venv）：
  // 入口必须走跨平台解释器解析器，而不是赌 PATH 上恰好有 python。
  assert.doesNotMatch(entry, /(^|\s)python3?(\s|$)/, "不得直接依赖裸 python");
  assert.match(entry, /run-python\.mjs\s+tests\/e2e\/learner-state-closed-loop\.py/);
  assert.match(packageJson.scripts["test:all"], /test:e2e:learner-state/);
});

test("every E2E package entry resolves the Python interpreter portably", () => {
  const entries = Object.entries(packageJson.scripts).filter(([name]) => name.startsWith("test:e2e:"));
  assert.ok(entries.length >= 3, "E2E 入口不应只剩一个");
  for (const [name, command] of entries) {
    assert.doesNotMatch(command, /(^|\s)python3?(\s|$)/, `${name} 不得直接调用裸 python`);
    assert.match(command, /^node scripts\/run-python\.mjs /, `${name} 必须走 run-python.mjs`);
  }
});
