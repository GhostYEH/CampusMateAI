import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("student home coordinates the simple and gamified presentations", async () => {
  const entry = await readFile(path.join(webRoot, "src", "views", "student", "StudentHomeView.vue"), "utf8");
  const home = await readFile(path.join(webRoot, "src", "components", "home", "ClassicStudentHome.vue"), "utf8");
  const command = await readFile(path.join(webRoot, "src", "components", "home", "HomeLearningCommand.vue"), "utf8");
  const schedule = await readFile(path.join(webRoot, "src", "components", "home", "HomeSchedulePanel.vue"), "utf8");

  assert.match(entry, /useStudentDashboardData/, "route view should use the shared dashboard coordinator");
  assert.match(entry, /ClassicStudentHome/, "route view should retain the simple presentation through the compatible component name");
  assert.match(entry, /GamifiedStudentHome/, "route view should select the gamified presentation independently");
  assert.doesNotMatch(entry, /getStudentDashboard/, "route view should not own API requests");
  assert.match(home, /HomeLearningCommand/, "simple home should lead with a derived learning action");
  assert.match(home, /HomeLearningPulse/, "simple home should summarize shared campus facts");
  assert.doesNotMatch(home, /hitokoto|CampusHotPostsPanel/, "simple home should not fetch or render unrelated content");
  assert.match(command, /Campus Agent/, "the command should explain the campus agent action path");
  assert.match(schedule, /schedule-empty-art/, "course empty state should use a transparent inline illustration");
  assert.match(schedule, /reference-schedule-week/, "course empty state should retain the reference weekly timeline");
  assert.doesNotMatch(schedule, /home-reference-schedule-empty\.png/, "course empty state should not use a rectangular raster image");
  assert.match(schedule, /暂无课程安排，假期或未选课/, "course empty state should use the reference copy");
  assert.match(home, /\/community/, "campus community should remain available as one secondary route");
  assert.match(home, /@media \(max-width: 700px\)/, "simple home composition should support narrow screens");
});
