import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const styles = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");

test("study metric icons keep their SVG centered inside the icon tile", () => {
  const iconRule = styles.match(/\.study-page \.stat-card \.stat-icon\s*\{([\s\S]*?)\n\}/)?.[1] || "";

  assert.match(iconRule, /display:\s*grid/);
  assert.match(iconRule, /place-items:\s*center/);
});
