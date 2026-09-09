import test from "node:test";
import assert from "node:assert/strict";
import { getDockScale } from "../src/components/FloatingNav/layout.js";

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
