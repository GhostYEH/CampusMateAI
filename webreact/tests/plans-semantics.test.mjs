import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const subpages = await readFile(new URL("../src/pages/StudySubpages.jsx", import.meta.url), "utf8");

test("plans page reports task counts honestly instead of fake plan counts", () => {
  assert.doesNotMatch(subpages, /Stat label=[""]全部计划/);
  assert.match(subpages, /Stat label=[""]学习任务/);
  assert.match(subpages, /Stat label=[""]待完成/);
  assert.match(subpages, /Stat label=[""]已完成/);
  // 不再把任务标题误称为“计划”
  assert.match(subpages, /未命名任务/);
  assert.doesNotMatch(subpages, /还没有计划/);
});

test("plans page surfaces the contract gap instead of pretending a plan model exists", () => {
  assert.match(subpages, /「计划 → 子任务 \+ 独立进度」的完整计划模型后端暂未提供/);
  assert.match(subpages, /source_name/);
});

test("AI planner reuses the existing task-breakdown endpoint with preview/edit/delete/confirm", () => {
  assert.match(subpages, /api\.breakdownStudyTask\(\{ goal: goal\.trim\(\) \}\)/);
  assert.match(subpages, /updateStep\(index, patch\)/);
  assert.match(subpages, /removeStep\(index\)/);
  assert.match(subpages, /confirmSaveSteps/);
  assert.match(subpages, /api\.createTask/);
  assert.match(subpages, /mode === [""]rule_fallback[""]/);
  assert.match(subpages, /userErrorMessage\(err, "目标拆解失败，请重试"\)/);
});