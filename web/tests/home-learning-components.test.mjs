import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("learning command exposes one action path and the agent loop", async () => {
  const source = await readFile(path.join(webRoot, "src", "components", "home", "HomeLearningCommand.vue"), "utf8");

  assert.match(source, /defineProps/);
  assert.match(source, /defineEmits\(\["navigate"\]\)/);
  assert.match(source, /观察/);
  assert.match(source, /分析/);
  assert.match(source, /计划/);
  assert.match(source, /执行/);
  assert.match(source, /command\.primaryAction\.path/);
  assert.match(source, /command\.secondaryAction\.path/);
  assert.doesNotMatch(source, /studentApi|services\/api|axios/);
});

test("learning pulse stays presentational and forwards existing routes", async () => {
  const source = await readFile(path.join(webRoot, "src", "components", "home", "HomeLearningPulse.vue"), "utf8");

  assert.match(source, /v-for="item in items"/);
  assert.match(source, /item\.label/);
  assert.match(source, /item\.value/);
  assert.match(source, /item\.detail/);
  assert.match(source, /emit\("navigate", path\)/);
  assert.doesNotMatch(source, /studentApi|services\/api|axios|localStorage/);
});

test("both home learning components include responsive and focus-visible styling", async () => {
  const sources = await Promise.all([
    "HomeLearningCommand.vue",
    "HomeLearningPulse.vue",
  ].map((file) => readFile(path.join(webRoot, "src", "components", "home", file), "utf8")));
  const combined = sources.join("\n");

  assert.match(combined, /:focus-visible/);
  assert.match(combined, /@media \(max-width: 700px\)/);
  assert.match(combined, /prefers-reduced-motion/);
});
