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

test("the courses page renders an animated scroll list with stable course ids and four sort modes", () => {
  assert.doesNotMatch(pageSource, /react-flip-toolkit/);
  assert.match(pageSource, /from "\.\.\/components\/AnimatedList\.jsx"/);
  assert.match(pageSource, /<AnimatedList[\s\S]*items=\{visible\}/);
  assert.match(pageSource, /topFadeOnScroll/);
  assert.match(pageSource, /renderItem=\{\(course\)/);
  assert.match(pageSource, /onItemSelect=\{\(course\) => navigate/);
  assert.match(pageSource, /enableArrowNavigation=\{!motionReduced\}/);
  assert.match(pageSource, /name-asc/);
  assert.match(pageSource, /name-desc/);
  assert.match(pageSource, /date-asc/);
  assert.match(pageSource, /date-desc/);
  assert.match(pageSource, /prefers-reduced-motion/);
  assert.doesNotMatch(animatedListSource, /react-flip-toolkit/);
  assert.match(animatedListSource, /layout=\{animateLayout \? "position" : false\}/);
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

test("the courses page keeps the header fixed while only the course list scrolls", () => {
  assert.match(pageSource, /className="courses-page__scroll-shell"/);
  assert.match(stylesSource, /\.courses-page\s*\{[\s\S]*height:\s*calc\(100dvh - 112px\)[\s\S]*overflow:\s*hidden/);
  assert.match(stylesSource, /\.courses-page__content\s*\{[\s\S]*min-height:\s*0/);
  assert.match(stylesSource, /\.courses-page__scroll-shell\s*\{[\s\S]*overflow:\s*hidden/);
  assert.match(stylesSource, /\.courses-page__scroll-shell > \.scroll-list-container\s*\{[\s\S]*height:\s*100%/);
  assert.match(stylesSource, /\.course-sort-list \.animated-list-scroll--grid\s*\{[\s\S]*height:\s*100%[\s\S]*overflow-y:\s*auto/);
  assert.match(stylesSource, /\.course-sort-list \.animated-list-scroll--top-fade\s*\{[\s\S]*var\(--animated-list-top-alpha, 1\)[\s\S]*var\(--animated-list-mid-alpha, 1\)[\s\S]*#000 112px/);
  assert.doesNotMatch(stylesSource, /\.courses-page__scroll-shell::before/);
  assert.match(animatedListSource, /scrollTop \/ 112/);
  assert.match(animatedListSource, /--animated-list-top-alpha/);
  assert.match(animatedListSource, /--animated-list-mid-alpha/);
});
