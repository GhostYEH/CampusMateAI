import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const css = readFileSync(resolve(root, "src/styles/home-classic.css"), "utf8");

test("classic React home has styles for its current layout", () => {
  for (const selector of [
    ".simple-home-command-stack",
    ".simple-home-grid",
    ".simple-priority-panel",
    ".simple-quick-section",
    ".simple-home-skeleton",
  ]) {
    assert.ok(css.includes(selector), selector);
  }
});
