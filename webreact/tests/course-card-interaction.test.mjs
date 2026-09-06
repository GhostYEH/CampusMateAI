import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { getCourseCardPointerStyle } from "../src/features/courses/courseCardInteraction.js";
import * as courseCardInteraction from "../src/features/courses/courseCardInteraction.js";

const parityPageSource = fs.readFileSync(new URL("../src/pages/ParityPages.jsx", import.meta.url), "utf8");
const stylesSource = fs.readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");

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

test("the live courses route uses the interactive course card and no legacy hero", () => {
  assert.match(parityPageSource, /import \{ CourseCard \} from .*CourseCard\.jsx/);
  assert.match(parityPageSource, /<CourseCard[\s\S]*progress=/);
  assert.doesNotMatch(parityPageSource, /asset-page-hero/);
});

test("the courses Grainient keeps a visible flowing texture behind the cards", () => {
  assert.match(parityPageSource, /timeSpeed=\{0\.28\}/);
  assert.match(parityPageSource, /warpStrength=\{1\.15\}/);
  assert.match(parityPageSource, /grainAmount=\{0\.02\}/);
  assert.match(parityPageSource, /renderScale=\{0\.6\}/);
  assert.match(parityPageSource, /frameRate=\{30\}/);
  assert.match(stylesSource, /\.courses-page \.courses-grainient \{[\s\S]*?opacity: \.72;/);
});

test("course cards forward FLIP data attributes to the rendered link", () => {
  const courseCardSource = fs.readFileSync(new URL("../src/components/CourseCard.jsx", import.meta.url), "utf8");

  assert.match(courseCardSource, /\.\.\.props/);
  assert.match(courseCardSource, /<Link[\s\S]*\.\.\.props/);
});
