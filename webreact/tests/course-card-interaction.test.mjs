import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { getCourseCardPointerStyle } from "../src/features/courses/courseCardInteraction.js";
import * as courseCardInteraction from "../src/features/courses/courseCardInteraction.js";

const parityPageSource = fs.readFileSync(new URL("../src/pages/ParityPages.jsx", import.meta.url), "utf8");
const stylesSource = fs.readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
const appShellSource = fs.readFileSync(new URL("../src/components/AppShell.jsx", import.meta.url), "utf8");

test("maps the pointer to a bounded card spotlight without vertical translation", () => {
  const style = getCourseCardPointerStyle(
    { clientX: 180, clientY: 80 },
    { left: 80, top: 20, width: 200, height: 120 },
  );

  assert.deepEqual(style, {
    pointerX: "50%",
    pointerY: "50%",
    tiltX: "0deg",
    tiltY: "0deg",
  });
});

test("clamps the pointer effect at the card edges", () => {
  const style = getCourseCardPointerStyle(
    { clientX: 999, clientY: -50 },
    { left: 80, top: 20, width: 200, height: 120 },
  );

  assert.equal(style.pointerX, "100%");
  assert.equal(style.pointerY, "0%");
  assert.equal(style.tiltX, "6deg");
  assert.equal(style.tiltY, "6deg");
});

test("keeps course identity, teaching information and progress in the redesigned card", () => {
  assert.equal(typeof courseCardInteraction.getCourseCardPresentation, "function");
  assert.deepEqual(
    courseCardInteraction.getCourseCardPresentation({
      code: "CS101",
      name: "程序设计基础",
      teacher_name: "陈老师",
      schedule: "周三 3-4 节",
    }, 63),
    {
      code: "CS101",
      name: "程序设计基础",
      teacher: "陈老师",
      detail: "周三 3-4 节",
      progress: 63,
      progressText: "63% 提交进度",
    },
  );
});

test("the live courses route uses the native OpenMAIC home and no legacy card grid", () => {
  assert.match(parityPageSource, /OpenMAICHome/);
  assert.match(parityPageSource, /api\.listInteractiveClassrooms/);
  assert.doesNotMatch(parityPageSource, /<AnimatedList/);
  assert.doesNotMatch(parityPageSource, /asset-page-hero/);
});

test("the courses page keeps its Iridescence background without mounting it on the Sylva homepage", () => {
  assert.doesNotMatch(parityPageSource, /Grainient/);
  assert.doesNotMatch(parityPageSource, /TargetCursor/);
  assert.match(appShellSource, /const isCourses = location\.pathname\.startsWith\("\/courses"\)/);
  assert.match(appShellSource, /isCourses && <Iridescence/);
  assert.match(appShellSource, /isCourses \? "iridescence-background-active"/);
  assert.doesNotMatch(appShellSource, /\(isHome \|\| isCourses\) && <Iridescence/);
});

test("course cards forward FLIP data attributes to the rendered link", () => {
  const courseCardSource = fs.readFileSync(new URL("../src/components/CourseCard.jsx", import.meta.url), "utf8");

  assert.match(courseCardSource, /\.\.\.props/);
  assert.match(courseCardSource, /<Link[\s\S]*\.\.\.props/);
});

test("course cards use a layered liquid-glass surface treatment", () => {
  const profileCardStyles = stylesSource.slice(
    stylesSource.indexOf(".courses-page .course-card.course-profile-card {"),
    stylesSource.indexOf("@media (max-width: 1800px)")
  );

  assert.match(profileCardStyles, /min-height:\s*250px/);
  assert.match(profileCardStyles, /aspect-ratio:\s*\.95/);
  assert.match(profileCardStyles, /background:\s*rgba\(255, 255, 255, \.1\)/);
  assert.match(profileCardStyles, /backdrop-filter:\s*blur\(14px\) saturate\(1\.4\)/);
  assert.match(profileCardStyles, /-webkit-backdrop-filter:\s*blur\(14px\) saturate\(1\.4\)/);
  assert.doesNotMatch(profileCardStyles, /rgba\(12, 18, 50, \.13\)/);
  assert.doesNotMatch(profileCardStyles, /rgba\(27, 39, 83, \.12\)/);
  assert.doesNotMatch(profileCardStyles, /rgba\(25, 35, 75, \.92\)/);
  assert.doesNotMatch(profileCardStyles, /rgba\(26, 38, 82, \.86\)/);
  assert.match(profileCardStyles, /\.course-profile-card__surface::before/);
  assert.match(profileCardStyles, /\.course-profile-card__surface::after/);
  assert.doesNotMatch(stylesSource, /\.courses-page \.course-card::before/);
  assert.doesNotMatch(stylesSource, /\.courses-page \.course-card\.course-profile-card::before/);
  assert.doesNotMatch(stylesSource, /\.course-profile-card__noise\s*\{/);
});
