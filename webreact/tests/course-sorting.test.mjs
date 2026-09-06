import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { sortCourses } from "../src/features/courses/courseSorting.js";

const pageSource = fs.readFileSync(new URL("../src/pages/ParityPages.jsx", import.meta.url), "utf8");

const courses = [
  { id: "algorithms", name: "Algorithms", last_synced_at: "2026-09-03T10:00:00Z", updated_at: "2026-09-03T10:00:00Z" },
  { id: "art", name: "Art History", last_synced_at: "2026-09-05T10:00:00Z", updated_at: "2026-09-05T10:00:00Z" },
  { id: "english", name: "English Writing", created_at: "2026-09-01T10:00:00Z", updated_at: "2026-09-02T10:00:00Z" },
  { id: "missing-date", name: "Data Structures", updated_at: "not-a-date", created_at: "2026-09-04T10:00:00Z" },
];

test("sorts courses by name in both directions without mutating the source", () => {
  const ascending = sortCourses(courses, "name-asc");
  const descending = sortCourses(courses, "name-desc");

  assert.deepEqual(ascending.map((course) => course.id), ["algorithms", "art", "missing-date", "english"]);
  assert.deepEqual(descending.map((course) => course.id), ["english", "missing-date", "art", "algorithms"]);
  assert.deepEqual(courses.map((course) => course.id), ["algorithms", "art", "english", "missing-date"]);
});

test("sorts courses by the newest available date in both directions", () => {
  const newestFirst = sortCourses(courses, "date-desc");
  const oldestFirst = sortCourses(courses, "date-asc");

  assert.deepEqual(newestFirst.map((course) => course.id), ["art", "missing-date", "algorithms", "english"]);
  assert.deepEqual(oldestFirst.map((course) => course.id), ["english", "algorithms", "missing-date", "art"]);
});

test("the courses page exposes FLIP animation with stable course ids and four sort modes", () => {
  assert.match(pageSource, /react-flip-toolkit/);
  assert.match(pageSource, /<Flipper[\s\S]*flipKey=/);
  assert.match(pageSource, /<Flipped[\s\S]*flipId=\{`course-\$\{course\.id\}`\}/);
  assert.match(pageSource, /name-asc/);
  assert.match(pageSource, /name-desc/);
  assert.match(pageSource, /date-asc/);
  assert.match(pageSource, /date-desc/);
  assert.match(pageSource, /prefers-reduced-motion/);
  assert.match(pageSource, /flipKey=\{motionReduced \?/);
});

test("the courses toolbar uses flat targetable sort buttons without a course search field", () => {
  assert.doesNotMatch(pageSource, /placeholder="搜索课程名称、代码或教师"/);
  assert.doesNotMatch(pageSource, /<select aria-label="课程排序"/);
  assert.match(pageSource, /role="group" aria-label="课程排序"/);
  assert.match(pageSource, /data-target-cursor/);
  for (const option of ["name-asc", "name-desc", "date-desc", "date-asc"]) {
    assert.match(pageSource, new RegExp(`value: "${option}"`));
  }
});
