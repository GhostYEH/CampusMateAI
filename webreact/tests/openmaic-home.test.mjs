import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import {
  FUSION_STATES,
  buildCourseRailItems,
  describeFusionState,
  filterOpenMAICHomeItems,
  normalizeRecentItems,
} from "../src/features/openmaic/homeModel.js";

const pageSource = fs.readFileSync(new URL("../src/pages/ParityPages.jsx", import.meta.url), "utf8");
const homeSource = fs.readFileSync(new URL("../src/components/openmaic/OpenMAICHome.jsx", import.meta.url), "utf8");
const courseDetailSource = fs.readFileSync(new URL("../src/pages/CourseDetailPage.jsx", import.meta.url), "utf8");

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

test("recent items keep the server order instead of re-sorting on the client", () => {
  const items = normalizeRecentItems({
    items: [
      { id: "s1", course_id: "c1", course_name: "数据结构", title: "自适应学习课堂", updated_at: "2026-09-02T10:00:00Z" },
      { id: "s2", course_id: "c2", course_name: "英语", title: "练习测验与即时反馈", updated_at: "2026-09-01T10:00:00Z" },
    ],
  });

  assert.deepEqual(items.map((item) => item.id), ["s1", "s2"]);
  assert.equal(items[0].courseId, "c1");
  assert.equal(items[0].href, "/courses/c1");
});

test("recent items carry the server deep link and never invent one", () => {
  const items = normalizeRecentItems({
    items: [{
      id: "s1",
      course_id: "c1",
      course_name: "数据结构",
      title: "自适应学习课堂",
      href: "/courses/c1?tab=mentoring&session=s1",
      classroom_url: "https://classroom.example.com/c/1",
      updated_at: "2026-09-02T10:00:00Z",
    }],
  });
  assert.equal(items[0].href, "/courses/c1?tab=mentoring&session=s1");
  assert.equal(items[0].classroomUrl, "https://classroom.example.com/c/1");
});

test("recent items tolerate an unexpected payload shape", () => {
  assert.deepEqual(normalizeRecentItems(null), []);
  assert.deepEqual(normalizeRecentItems({}), []);
  assert.deepEqual(normalizeRecentItems({ items: [null, {}, { id: "" }] }), []);
});

test("fusion state distinguishes disabled, unavailable, degraded and ready", () => {
  assert.deepEqual(FUSION_STATES, ["disabled", "unavailable", "degraded", "ready"]);
  const labels = FUSION_STATES.map((state) => describeFusionState({ state, capabilities: [] }).label);
  assert.equal(new Set(labels).size, FUSION_STATES.length);
});

test("only the ready state opens entry points, and only for advertised capabilities", () => {
  const ready = describeFusionState({ state: "ready", capabilities: ["workspace", "folder"] });
  assert.equal(ready.canCreateWorkspace, true);
  assert.equal(ready.canBrowseFolders, true);
  assert.equal(ready.canSearch, false);
  assert.equal(ready.canImport, false);

  for (const state of ["disabled", "unavailable", "degraded"]) {
    const view = describeFusionState({ state, capabilities: ["workspace", "folder", "search", "import-pptx"] });
    assert.deepEqual(view.capabilities, [], state);
    assert.equal(view.canCreateWorkspace, false, state);
    assert.equal(view.canBrowseFolders, false, state);
    assert.equal(view.canSearch, false, state);
    assert.equal(view.canImport, false, state);
  }
});

test("an unknown or missing fusion state is reported as unavailable, not as ready", () => {
  for (const payload of [null, undefined, {}, { state: "who-knows" }]) {
    const view = describeFusionState(payload);
    assert.equal(view.state, "unavailable");
    assert.deepEqual(view.capabilities, []);
  }
});

test("home search filters only records supplied by the server", () => {
  const results = filterOpenMAICHomeItems(
    [{ id: "s1", courseName: "数据结构", title: "复习课堂" }],
    "数据",
  );
  assert.equal(results.length, 1);
  assert.deepEqual(filterOpenMAICHomeItems([], "数据"), []);
});

test("courses route calls the aggregate endpoints instead of per-course history", () => {
  assert.match(pageSource, /OpenMAICHome/);
  assert.match(pageSource, /api\.getOpenMAICRecent\(/);
  assert.match(pageSource, /api\.getOpenMAICFusionStatus\(/);
  assert.match(pageSource, /api\.getCourses\(\)/);
  assert.match(pageSource, /api\.getAssignments\(\)/);
  // 旧的"对前 12 门课程各发一次历史请求"必须消失
  assert.doesNotMatch(pageSource, /listInteractiveClassrooms/);
  assert.doesNotMatch(pageSource, /slice\(0,\s*12\)/);
  assert.doesNotMatch(pageSource, /<AnimatedList/);
});

test("home surface exposes no placeholder entries and no iframe", () => {
  assert.match(homeSource, /aria-label="OpenMAIC 学习工作台"/);
  assert.match(homeSource, /快速询问/);
  assert.match(homeSource, /describeFusionState/);
  assert.doesNotMatch(homeSource, /正在接入/);
  assert.doesNotMatch(homeSource, /iframe/);
});

test("course detail honours the native deep link from the recent list", () => {
  assert.match(courseDetailSource, /useSearchParams/);
  assert.match(courseDetailSource, /searchParams\.get\("tab"\)/);
  assert.match(courseDetailSource, /searchParams\.get\("session"\)/);
  assert.match(courseDetailSource, /initialSessionId=\{deepLinkSession\}/);
});
