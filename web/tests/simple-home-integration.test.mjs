import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("simple home composes one learning command from the shared coordinator", async () => {
  const [home, coordinator] = await Promise.all([
    readFile(path.join(webRoot, "src/components/home/ClassicStudentHome.vue"), "utf8"),
    readFile(path.join(webRoot, "src/composables/useStudentDashboardData.js"), "utf8"),
  ]);

  assert.match(home, /HomeLearningCommand/);
  assert.match(home, /HomeLearningPulse/);
  assert.match(home, /state\.learningCommand/);
  assert.match(coordinator, /resolveHomeLearningCommand/);
  assert.match(coordinator, /learningCommand/);
  assert.doesNotMatch(home, /CampusHotPostsPanel|hitokoto|home-reference-hero-calendar/);
  assert.doesNotMatch(coordinator, /getCommunityPosts|fetchHitokoto/);
});

test("primary learning routes are not repeated in secondary quick links", async () => {
  const source = await readFile(path.join(webRoot, "src/components/home/ClassicStudentHome.vue"), "utf8");
  const quickLinksBlock = source.match(/const quickLinks = \[([\s\S]*?)\];/)?.[1] || "";

  assert.doesNotMatch(quickLinksBlock, /\/courses|\/tasks|\/study|\/counselor|\/exams/);
  assert.match(quickLinksBlock, /\/services/);
  assert.match(quickLinksBlock, /\/community/);
});

test("simple remains the user-facing default while classic stays the storage value", async () => {
  const [settings, dashboardStyle] = await Promise.all([
    readFile(path.join(webRoot, "src/views/student/StudentSettingsView.vue"), "utf8"),
    readFile(path.join(webRoot, "src/features/dashboard/dashboardStyle.js"), "utf8"),
  ]);

  assert.match(settings, /<strong>简洁<\/strong>/);
  assert.match(settings, /简洁首页已启用/);
  assert.match(dashboardStyle, /return value === "gamified" \? "gamified" : "classic"/);
});

test("game presentation remains wired to the same dashboard coordinator", async () => {
  const entry = await readFile(path.join(webRoot, "src/views/student/StudentHomeView.vue"), "utf8");

  assert.match(entry, /useStudentDashboardData/);
  assert.match(entry, /ClassicStudentHome/);
  assert.match(entry, /GamifiedStudentHome/);
  assert.equal((entry.match(/useStudentDashboardData\(/g) || []).length, 1);
});
