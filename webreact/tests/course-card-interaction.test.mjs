import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { getCourseCardPointerStyle } from "../src/features/courses/courseCardInteraction.js";

const parityPageSource = fs.readFileSync(new URL("../src/pages/ParityPages.jsx", import.meta.url), "utf8");

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

test("the live courses route uses the interactive course card and no legacy hero", () => {
  assert.match(parityPageSource, /import \{ CourseCard \} from .*CourseCard\.jsx/);
  assert.match(parityPageSource, /<CourseCard[\s\S]*progress=/);
  assert.doesNotMatch(parityPageSource, /asset-page-hero/);
});
