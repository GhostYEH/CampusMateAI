import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const gamifiedRoot = path.join(webRoot, "src", "components", "home", "gamified");

test("gamified dashboard is composed as a campus RPG interface with canonical routes", async () => {
  const componentNames = [
    "GamifiedStudentHome.vue",
    "CharacterPanel.vue",
    "AdventureWorld.vue",
    "WorldMapNavigation.vue",
    "QuestLog.vue",
    "CampusMap.vue",
    "AICompanion.vue",
    "GrowthTree.vue",
    "AchievementHall.vue",
    "DailySignIn.vue",
  ];
  const files = await Promise.all(componentNames.map((name) => readFile(path.join(gamifiedRoot, name), "utf8")));
  const source = files.join("\n");

  for (const label of ["角色档案", "今日校园冒险", "任务日志", "校园地图", "AI 伙伴", "成长轨迹", "荣誉大厅", "每日签到", "校园世界"]) {
    assert.match(source, new RegExp(label), `missing gamified section: ${label}`);
  }
  for (const route of ["/home", "/courses", "/tasks", "/exams", "/study", "/counselor", "/classrooms", "/community", "/profile", "/profile/settings", "/services", "/lostfound"]) {
    assert.match(source, new RegExp(route.replaceAll("/", "\\/")), `world map should reuse route ${route}`);
  }
  assert.match(source, /fallback-avatar\.png/);
  assert.doesNotMatch(source, /<iframe/, "the homepage should not load the full Unity runtime before the user opens the counselor");
  assert.doesNotMatch(source, /PhRobot/, "the gamified home must use the CPM digital human instead of a robot placeholder");
  assert.match(source, /role="dialog"/);
  assert.match(source, /aria-modal="true"/);
  assert.match(source, /BOSS CHALLENGE|Boss Challenge/);
  assert.match(source, /WORLD EVENTS/);
  assert.doesNotMatch(source, /services\/studentApi|getStudentDashboard|fetch\(/, "presentation components must not fetch business data");
});

test("gamified mode owns the full shell while classic mode keeps the normal navigation", async () => {
  const [shell, home] = await Promise.all([
    readFile(path.join(webRoot, "src", "views", "AppShell.vue"), "utf8"),
    readFile(path.join(webRoot, "src", "views", "student", "StudentHomeView.vue"), "utf8"),
  ]);

  assert.match(shell, /gamified-home-mode/);
  assert.match(shell, /store\.dashboardStyle\s*===\s*["']gamified["']/);
  assert.match(home, /v-if="store\.dashboardStyle === 'gamified'"/);
  assert.match(home, /ClassicStudentHome/);
});

test("gamified visual system supports narrow screens and reduced motion", async () => {
  const styles = await readFile(path.join(webRoot, "src", "styles", "student-home-gamified.css"), "utf8");
  const main = await readFile(path.join(webRoot, "src", "main.js"), "utf8");

  assert.match(main, /student-home-gamified\.css/);
  assert.match(styles, /@media\s*\(max-width:\s*760px\)/);
  assert.match(styles, /@media\s*\(prefers-reduced-motion:\s*reduce\)/);
  assert.match(styles, /--game-xp:/, "XP color should be a semantic token");
  assert.match(styles, /--game-streak:/, "streak color should be a semantic token");
  assert.match(styles, /--game-world:/, "campus world background should be a semantic token");
  assert.match(styles, /--game-cyan:/, "HUD accent should be a semantic token");
  assert.match(styles, /\.app-layout\.student-layout\.gamified-home-mode\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s*!important/s, "gamified shell must override the later desktop layout-system rule");
});
