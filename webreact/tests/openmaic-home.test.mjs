import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import {
  buildCourseRailItems,
  buildRecentClassrooms,
  filterOpenMAICHomeItems,
} from "../src/features/openmaic/homeModel.js";

const pageSource = fs.readFileSync(new URL("../src/pages/ParityPages.jsx", import.meta.url), "utf8");
const homeSource = fs.readFileSync(new URL("../src/components/openmaic/OpenMAICHome.jsx", import.meta.url), "utf8");

test("course rail uses real course identity and pending assignment deadlines", () => {
  const items = buildCourseRailItems([
    { id: "c1", name: "数据结构", code: "CS201", teacher_name: "王老师", semester: "2026 春" },
  ], [
    { id: "a1", course_id: "c1", title: "实验一", deadline: "2026-09-20T10:00:00Z", submission_status: "draft" },
    { id: "a2", course_id: "c1", title: "实验零", deadline: "2026-09-10T10:00:00Z", submission_status: "submitted" },
  ]);

  assert.deepEqual(items[0], {
    id: "c1",
    name: "数据结构",
    code: "CS201",
    teacher: "王老师",
    term: "2026 春",
    pendingCount: 1,
    nextDeadline: "2026-09-20T10:00:00Z",
  });
});

test("recent classrooms are real records sorted by updated time and scoped to a course", () => {
  const recent = buildRecentClassrooms([
    { courseId: "c1", items: [{ session_id: "s1", title: "复习课堂", updated_at: "2026-09-02T10:00:00Z" }] },
    { courseId: "c2", items: [{ session_id: "s2", title: "旧课堂", updated_at: "2026-09-01T10:00:00Z" }] },
  ]);

  assert.deepEqual(recent.map((item) => item.session_id), ["s1", "s2"]);
  assert.equal(recent[0].courseId, "c1");
});

test("home search filters only records supplied by the server", () => {
  const results = filterOpenMAICHomeItems(
    [{ session_id: "s1", courseName: "数据结构", title: "复习课堂" }],
    "数据",
  );
  assert.equal(results.length, 1);
  assert.deepEqual(filterOpenMAICHomeItems([], "数据"), []);
});

test("courses route renders native OpenMAIC home surfaces and real APIs", () => {
  assert.match(pageSource, /OpenMAICHome/);
  assert.match(pageSource, /api\.listInteractiveClassrooms/);
  assert.match(pageSource, /api\.getCourses\(\)/);
  assert.match(pageSource, /api\.getAssignments\(\)/);
  assert.doesNotMatch(pageSource, /<AnimatedList/);
  assert.match(homeSource, /aria-label="OpenMAIC 学习工作台"/);
  assert.match(homeSource, /快速询问/);
  assert.match(homeSource, /导入能力正在接入/);
  assert.doesNotMatch(homeSource, /iframe/);
});
