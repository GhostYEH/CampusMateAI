import assert from "node:assert/strict";
import { test } from "node:test";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("study dashboard exposes all six interactive secondary experiences", async () => {
  const [view, layer, css] = await Promise.all([
    readFile(path.join(webRoot, "src/views/student/StudentStudyView.vue"), "utf8"),
    readFile(path.join(webRoot, "src/components/study/StudyExperienceLayer.vue"), "utf8"),
    readFile(path.join(webRoot, "src/styles/study-secondary.css"), "utf8"),
  ]);

  for (const kind of ["focus", "plan", "metric", "record", "trend", "task"]) {
    assert.match(view, new RegExp(`openExperience\\([\\s\\S]*[\"']${kind}[\"']`));
    assert.match(layer, new RegExp(`view === [\"']${kind}[\"']`));
  }
  assert.match(layer, /role="dialog"/);
  assert.match(layer, /@keydown\.esc="close"/);
  assert.match(layer, /study-magnetic/);
  assert.match(layer, /rangeOptions/);
  assert.match(layer, /emit\(["']complete-task["']/);
  assert.match(css, /@keyframes study-layer-reveal/);
  assert.match(css, /@keyframes study-orbit/);
  assert.match(css, /@keyframes study-particle-flight/);
  assert.match(css, /prefers-reduced-motion:reduce/);
});
