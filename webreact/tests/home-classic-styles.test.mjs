import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../src/styles/home-classic.css", import.meta.url), "utf8");

test("the retained homepage pulse has its visual styles without obsolete command styles", () => {
  assert.match(source, /\.home-learning-pulse\{[^}]*display:grid[^}]*border-radius:/);
  assert.match(source, /\.pulse-grid\{[^}]*display:grid/);
  assert.doesNotMatch(source, /\.home-learning-command|\.home-command-mesh|\.home-agent-loop/);
  assert.doesNotMatch(source, /\.simple-priority-panel/);
  assert.doesNotMatch(source, /\.simple-home-command-stack|\.simple-home-grid|\.simple-quick-section/);
});
