import assert from "node:assert/strict";
import test from "node:test";
import { isSummerNavActive, SUMMER_NAV_LINKS } from "../src/features/study/summerNav.js";

test("summer secondary navigation maps to the migrated companion routes", () => {
  assert.deepEqual(SUMMER_NAV_LINKS.map((item) => item.to), ["/island", "/plans", "/docs", "/statistics"]);
  assert.deepEqual(SUMMER_NAV_LINKS.map((item) => item.label), ["小岛", "计划", "阅读", "统计"]);
});

test("summer navigation stays active for nested detail routes", () => {
  assert.equal(isSummerNavActive("/docs/reading-1", "/docs"), true);
  assert.equal(isSummerNavActive("/courses/reading-1", "/docs"), false);
});
