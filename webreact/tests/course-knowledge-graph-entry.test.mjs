import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const read = (rel) => readFileSync(resolve(here, "..", rel), "utf8");

// 课程知识图谱在后端已全链路打通，但前端曾经零入口 —— 页面存在但用户进不去。
// 这里锁死"入口 + 真实取数"两件事。

test("课程详情页提供知识点掌握入口（tab + 概览卡）", () => {
  const page = read("src/pages/CourseDetailPage.jsx");
  assert.match(page, /\["knowledge",\s*"知识点掌握"\]/, "缺少知识点掌握 tab");
  assert.match(page, /onClick=\{\(\) => setTab\("knowledge"\)\}/, "概览缺少跳转入口");
});

test("知识点数据来自后端接口而不是写死", () => {
  const api = read("src/data/api.js");
  assert.match(api, /export async function getCourseKnowledgeGraph\(courseId\)/);
  assert.match(api, /\/courses\/\$\{courseId\}\/knowledge-graph/);

  const page = read("src/pages/CourseDetailPage.jsx");
  assert.match(page, /api\.getCourseKnowledgeGraph\(courseId\)/, "页面没有调用真实接口");
  assert.doesNotMatch(page, /knowledge_point_count:\s*\d/, "页面不应内联假数据");
});

test("同步知识点走 section 白名单，避免连带跑完整 deep 同步", () => {
  const page = read("src/pages/CourseDetailPage.jsx");
  assert.match(page, /syncCourse\(courseId,\s*"deep",\s*\["knowledge_graph"\]\)/);
});

test("未同步的课程给出可操作的同步入口而不是空白", () => {
  const page = read("src/pages/CourseDetailPage.jsx");
  assert.match(page, /!graph\.available/, "缺少未同步分支");
  assert.match(page, /同步知识点/);
});
