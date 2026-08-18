import assert from "node:assert/strict";
import { test } from "node:test";

import { groupScheduleByWeekday } from "../src/features/home/scheduleModel.js";

test("groups active schedule entries by weekday and sorts by class section", () => {
  const grouped = groupScheduleByWeekday([
    { id: "wed-late", weekday: 3, start_section: 5, course_name: "算法设计" },
    { id: "mon", weekday: 1, start_section: 1, course_name: "高等数学" },
    { id: "wed-early", weekday: 3, start_section: 3, course_name: "数据库原理" },
    { id: "stale", weekday: 2, start_section: 2, course_name: "旧课程", is_stale: true },
    { id: "invalid", weekday: 8, start_section: 1, course_name: "无效课程" },
  ]);

  assert.deepEqual(grouped[0].map((item) => item.id), ["mon"]);
  assert.deepEqual(grouped[2].map((item) => item.id), ["wed-early", "wed-late"]);
  assert.deepEqual(grouped[1], []);
  assert.equal(grouped.length, 7);
});
