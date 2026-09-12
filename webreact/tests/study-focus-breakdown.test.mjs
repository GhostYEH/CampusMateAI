import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const studyPage = await readFile(new URL("../src/pages/StudyPage.jsx", import.meta.url), "utf8");
const focusRoom = await readFile(new URL("../src/components/study/SummerFocusRoom.jsx", import.meta.url), "utf8");

test("focus goal opens an in-place AI task breakdown workflow", () => {
  assert.match(studyPage, /breakdownStudyTask/);
  assert.match(studyPage, /onBreakdown/);
  assert.match(studyPage, /breakdownSteps/);
  assert.match(focusRoom, /AI 拆解本次目标/);
  assert.match(focusRoom, /onOpenPlanning/);
});
