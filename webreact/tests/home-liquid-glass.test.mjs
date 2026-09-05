import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const command = await readFile(new URL("../src/pages/home/HomeLearningCommand.jsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles/home-classic.css", import.meta.url), "utf8");

test("classic homepage exposes a reduced-motion safe elastic mesh accent", () => {
  assert.match(command, /lazy\(\(\) => import\(["']\.\.\/\.\.\/components\/ElasticMesh\.jsx["']\)\)/);
  assert.match(command, /!reduceMotion && <ElasticMesh/);
  assert.match(command, /aria-hidden=["']true["']/);
});

test("classic homepage cards use a translucent glass treatment with a static fallback", () => {
  for (const selector of [
    ".simple-home-command-stack",
    ".simple-home-grid",
    ".simple-priority-panel",
    ".simple-quick-section",
  ]) {
    assert.ok(styles.includes(selector), selector);
  }
  assert.match(styles, /backdrop-filter:blur\(/);
  assert.match(styles, /@media\(prefers-reduced-motion:reduce\)/);
});
