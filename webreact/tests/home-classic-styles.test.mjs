import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../src/styles/home-classic.css", import.meta.url), "utf8");

test("classic homepage layout components have their visual styles", () => {
  assert.match(source, /\.home-learning-command\s*\{[^}]*position:relative[^}]*min-height:/);
  assert.match(source, /\.home-command-mesh\s*\{[^}]*position:absolute[^}]*inset:0/);
  assert.doesNotMatch(source, /\.simple-priority-panel/);
  assert.doesNotMatch(source, /\.simple-home-command-stack|\.simple-home-grid|\.simple-quick-section/);
});
