import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const studyPage = await readFile(new URL("../src/pages/StudyPage.jsx", import.meta.url), "utf8");

test("study companion applies the shared tilt interaction to every top-level card", () => {
  assert.match(studyPage, /import TiltedCard from ["']\.\.\/components\/TiltedCard\.jsx["']/);
  for (const className of [
    "study-focus-card",
    "study-report-card",
    "study-plan-card",
    "study-metric-card",
    "study-trend-card",
    "study-experience-card",
    "study-records-card",
    "study-tasks-card"
  ]) {
    assert.match(studyPage, new RegExp(`className=["']${className}["']`));
  }
  assert.match(studyPage, /function StudyTiltedCard/);
});
