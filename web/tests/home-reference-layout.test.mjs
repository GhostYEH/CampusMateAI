import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import { test } from "node:test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("student home renders the reference hero and visual empty states", async () => {
  const home = await readFile(path.join(webRoot, "src", "views", "student", "StudentHomeView.vue"), "utf8");
  const schedule = await readFile(path.join(webRoot, "src", "components", "home", "HomeSchedulePanel.vue"), "utf8");
  const styles = await readFile(path.join(webRoot, "src", "styles", "student-home.css"), "utf8");

  assert.match(home, /home-reference-hero-calendar\.png/, "hero should use the reference-style calendar artwork");
  assert.match(home, /reference-hero-weather/, "hero should include the reference weather line");
  assert.match(schedule, /schedule-empty-art/, "course empty state should use a transparent inline illustration");
  assert.match(schedule, /reference-schedule-week/, "course empty state should retain the reference weekly timeline");
  assert.doesNotMatch(schedule, /home-reference-schedule-empty\.png/, "course empty state should not use a rectangular raster image");
  assert.match(schedule, /暂无课程安排，假期或未选课/, "course empty state should use the reference copy");
  assert.match(home, /hot-empty-art/, "hot-topic empty state should use a transparent inline illustration");
  assert.doesNotMatch(home, /home-reference-hot-empty\.png/, "hot-topic empty state should not use a rectangular raster image");
  assert.match(home, /<text x="119" y="65"/, "hot-topic illustration should include the white hash mark");
  assert.match(styles, /reference-home-visual-system/, "reference visual-system styles should be present");

  await Promise.all([
    "home-reference-hero-calendar.png",
    "home-reference-schedule-empty.png",
    "home-reference-hot-empty.png",
    "home-reference-student-avatar.png",
  ].map((file) => access(path.join(webRoot, "public", "assets", "generated", file))));
});
