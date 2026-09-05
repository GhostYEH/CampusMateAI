import test from "node:test";
import assert from "node:assert/strict";
import { getDockScale, getFloatingNavWidth } from "../src/components/FloatingNav/layout.js";

test("dock scale follows pointer proximity and returns to base size outside its range", () => {
  assert.equal(getDockScale(0), 60 / 36);
  assert.equal(getDockScale(60), 1 + ((60 / 36) - 1) * 0.5);
  assert.equal(getDockScale(120), 1);
  assert.equal(getDockScale(240), 1);
});

test("dock scale stays conservative for invalid measurements", () => {
  assert.equal(getDockScale(Number.POSITIVE_INFINITY), 1);
  assert.equal(getDockScale(Number.NaN), 1);
  assert.equal(getDockScale(0, 0), 1);
  assert.equal(getDockScale(0, 120, 0), 1);
});

test("expanded floating navigation fits every desktop item without clipping", () => {
  const itemWidths = [78, 100, 100, 111, 133, 100, 100, 100];
  const contentWidth = itemWidths.reduce((total, width) => total + width, 0) + 7 * 4 + 18;

  assert.equal(getFloatingNavWidth({ contentWidth, viewportWidth: 1440 }), contentWidth);
  assert.ok(contentWidth > 820, "the regression fixture must exceed the old fixed width");
});

test("expanded floating navigation stays inside narrow viewport gutters", () => {
  assert.equal(getFloatingNavWidth({ contentWidth: 900, viewportWidth: 768 }), 744);
  assert.equal(getFloatingNavWidth({ contentWidth: 900, viewportWidth: 1200 }), 900);
});
