import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { sortCourses } from "../src/features/courses/courseSorting.js";

const pageSource = fs.readFileSync(new URL("../src/pages/ParityPages.jsx", import.meta.url), "utf8");
const animatedListSource = fs.readFileSync(new URL("../src/components/AnimatedList.jsx", import.meta.url), "utf8");
const stylesSource = fs.readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");

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

test("the courses page renders the native magic class command and real course rail", () => {
  assert.match(pageSource, /MagicClassHome/);
  assert.match(pageSource, /api\.getCourses\(\)/);
  assert.match(pageSource, /api\.getAssignments\(\)/);
  assert.doesNotMatch(pageSource, /<AnimatedList/);
  assert.match(fs.readFileSync(new URL("../src/components/magicclass/magicclassHome.jsx", import.meta.url), "utf8"), /我的课程/);
});

test("the courses home gates import and folder entries on real server capabilities", () => {
  const homeSource = fs.readFileSync(new URL("../src/components/magicclass/magicclassHome.jsx", import.meta.url), "utf8");
  // 入口是否可点只由服务端上报的 capability 决定，不出现"正在接入"这类占位文案，
  // 也不出现点了没反应的按钮。
  assert.match(homeSource, /magicclass-home--reference/);
  assert.match(homeSource, /api\.generateMagicClassHome/);
  assert.match(homeSource, /providerStatus\?\.providers\?\.llm/);
  assert.doesNotMatch(homeSource, /正在接入/);
  assert.doesNotMatch(homeSource, /TODO/);
});

test("the native home has responsive layouts for desktop, tablet and phone widths", () => {
  assert.match(stylesSource, /\.magicclass-home\s*\{[\s\S]*grid-template-columns/);
  assert.match(stylesSource, /@media \(max-width: 1024px\)[\s\S]*\.magicclass-home/);
  assert.match(stylesSource, /@media \(max-width: 767px\)[\s\S]*\.magicclass-home/);
  assert.match(stylesSource, /@media \(max-width: 360px\)[\s\S]*\.magicclass-command-panel/);
});
