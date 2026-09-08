import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const pulse = await readFile(new URL("../src/pages/home/HomeLearningPulse.jsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles/home-classic.css", import.meta.url), "utf8");

test("the current homepage pulse remains interactive and cursor reactive", () => {
  assert.match(pulse, /home-learning-pulse sylva-cursor-reactive/);
  assert.match(pulse, /items\.map/);
  assert.match(pulse, /onClick=\{\(\) => navigate\(item\.path\)\}/);
});

test("classic homepage cards use a translucent glass treatment without scroll-time backdrop filtering", () => {
  assert.match(styles, /\.home-learning-pulse\{[^}]*background:linear-gradient\(/);
  assert.match(styles, /\.home-learning-pulse\{[^}]*backdrop-filter:none/);
  assert.match(styles, /@media\(prefers-reduced-motion:reduce\)/);
});
