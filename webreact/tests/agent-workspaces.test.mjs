import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const root = new URL("../src/", import.meta.url);
const read = (file) => fs.readFileSync(new URL(file, root), "utf8");

test("agent API uses authenticated client and stable idempotency keys", () => {
  const source = read("data/agentApi.js");
  assert.match(source, /client\.post\("\/final-review\/campaigns"/);
  assert.match(source, /Idempotency-Key/);
  assert.match(source, /Last-Event-ID/);
});

test("final review and course research pages expose server policy and real ids", () => {
  const review = read("pages/FinalReviewPage.jsx");
  const research = read("pages/CourseResearchPage.jsx");
  assert.match(review, /exam_id: examId/);
  assert.match(review, /generatePlan/);
  assert.match(research, /academic_policy: "STANDARD"/);
  assert.match(research, /verification_status/);
  assert.match(research, /allow_web/);
});

test("new workspace routes are lazy and preloaded", () => {
  const app = read("App.jsx");
  const preload = read("app/routePreload.js");
  assert.match(app, /path="\/final-review"/);
  assert.match(app, /path="\/course-research"/);
  assert.match(preload, /"final-review"/);
  assert.match(preload, /"course-research"/);
});
