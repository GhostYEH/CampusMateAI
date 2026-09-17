import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { isSummerNavActive, SUMMER_NAV_LINKS } from "../src/features/study/summerNav.js";

const summerStyles = readFileSync(new URL("../src/styles/study-summer.css", import.meta.url), "utf8");
const floatingLayoutStyles = readFileSync(new URL("../src/styles/floating-layout.css", import.meta.url), "utf8");

test("summer secondary navigation maps to the migrated companion routes", () => {
  assert.deepEqual(SUMMER_NAV_LINKS.map((item) => item.to), ["/island", "/plans", "/docs", "/statistics"]);
  assert.deepEqual(SUMMER_NAV_LINKS.map((item) => item.label), ["小岛", "计划", "阅读", "统计"]);
});

test("summer navigation stays active for nested detail routes", () => {
  assert.equal(isSummerNavActive("/docs/reading-1", "/docs"), true);
  assert.equal(isSummerNavActive("/courses/reading-1", "/docs"), false);
});

test("summer dock owns its accent token so every study route renders the same active state", () => {
  assert.match(summerStyles, /.study-summer-dock\s*\{[^}]*--summer-primary:\s*#d7ef83;/s);
});

test("fixed navigation keeps its center when route content changes scrollbar state", () => {
  assert.match(floatingLayoutStyles, /html\s*\{[^}]*scrollbar-gutter:\s*stable;/s);
});

test("compact global and study navigation docks stack without moving either to the header", () => {
  assert.match(
    summerStyles,
    /@media \(max-width: 1439px\)[\s\S]*\.app-layout\.study-mode \.study-summer-dock\s*\{[^}]*bottom:\s*calc\(75px \+ env\(safe-area-inset-bottom\)\)/,
  );
  assert.doesNotMatch(
    summerStyles,
    /\.app-layout\.study-mode \.floating-nav[^}]*top:\s*max\(10px/,
  );
});
