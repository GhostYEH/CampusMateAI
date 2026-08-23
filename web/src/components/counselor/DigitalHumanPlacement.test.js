import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const view = readFileSync(new URL("../../views/student/StudentCounselorView.vue", import.meta.url), "utf8");
const panel = readFileSync(new URL("./DigitalHumanPanel.vue", import.meta.url), "utf8");

test("digital human replaces the campus services card in the right rail", () => {
  assert.doesNotMatch(view, /class="counselor-panel services-panel"/);
  assert.doesNotMatch(view, /const quickServices =/);
  assert.equal((view.match(/<DigitalHumanPanel/g) || []).length, 1);
});

test("prominent digital human stage is large enough to show facial motion", () => {
  assert.match(panel, /height:\s*430px/);
});
