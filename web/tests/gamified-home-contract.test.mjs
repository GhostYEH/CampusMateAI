import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const gamifiedRoot = path.join(webRoot, "src", "components", "home", "gamified");

test("gamified dashboard has independent accessible sections and canonical routes", async () => {
  const files = await Promise.all([
    "GamifiedStudentHome.vue",
    "PlayerHeader.vue",
    "DailyAdventureCard.vue",
    "MainQuestSection.vue",
    "GrowthAndAchievements.vue",
  ].map((name) => readFile(path.join(gamifiedRoot, name), "utf8")));
  const source = files.join("\n");

  for (const label of ["今日校园冒险", "今日主线", "校园探索", "本周成长", "最近获得", "校园世界"]) {
    assert.match(source, new RegExp(label), `missing gamified section: ${label}`);
  }
  for (const route of ["/study", "/counselor", "/classrooms", "/services", "/lostfound", "/exams"]) {
    assert.match(source, new RegExp(route), `side quest should reuse route ${route}`);
  }
  assert.match(source, /role="dialog"/);
  assert.match(source, /aria-modal="true"/);
  assert.doesNotMatch(source, /services\/studentApi|getStudentDashboard|fetch\(/, "presentation components must not fetch business data");
});

test("gamified visual system supports narrow screens and reduced motion", async () => {
  const styles = await readFile(path.join(webRoot, "src", "styles", "student-home-gamified.css"), "utf8");
  const main = await readFile(path.join(webRoot, "src", "main.js"), "utf8");

  assert.match(main, /student-home-gamified\.css/);
  assert.match(styles, /@media\s*\(max-width:\s*760px\)/);
  assert.match(styles, /@media\s*\(prefers-reduced-motion:\s*reduce\)/);
  assert.match(styles, /--game-xp:/, "XP color should be a semantic token");
  assert.match(styles, /--game-streak:/, "streak color should be a semantic token");
});
