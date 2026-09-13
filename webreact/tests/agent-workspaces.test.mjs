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
  const campaignForm = read("components/finalReview/FinalReviewCampaignForm.jsx");
  const researchForm = read("components/courseResearch/CourseResearchForm.jsx");
  const researchReport = read("components/courseResearch/CourseResearchReport.jsx");
  // 考试使用服务端 id，由表单映射为 exam_ids 后提交。
  assert.match(campaignForm, /exam_ids/);
  assert.match(review, /generateFinalReviewPlan/);
  // 来源策略由前端声明、学术政策由后端裁决，前端不自行推断完整答案。
  assert.match(researchForm, /source_policy/);
  assert.match(researchForm, /course_material_priority/);
  assert.match(researchForm, /allow_web/);
  assert.match(researchReport, /allowsFullSolution/);
});

test("new workspace routes are lazy and preloaded", () => {
  const app = read("App.jsx");
  const preload = read("app/routePreload.js");
  assert.match(app, /path="\/final-review"/);
  assert.match(app, /path="\/course-research"/);
  assert.match(preload, /"final-review"/);
  assert.match(preload, /"course-research"/);
});