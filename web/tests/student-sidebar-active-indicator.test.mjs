import assert from "node:assert/strict";
import { test } from "node:test";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function declarationsFor(css, selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = css.match(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`));
  assert.ok(match, `Missing CSS rule: ${selector}`);
  return match[1];
}

test("draws the active sidebar accent as a centered rounded bar", async () => {
  const css = await readFile(path.join(webRoot, "src", "styles", "student-redesign.css"), "utf8");
  const active = declarationsFor(css, ".student-layout .sidebar nav button.active");
  const indicator = declarationsFor(css, ".student-layout .sidebar nav button.active::before");

  assert.doesNotMatch(active, /box-shadow\s*:\s*inset/i);
  assert.match(active, /position\s*:\s*relative/i);
  assert.match(indicator, /width\s*:\s*3px/i);
  assert.match(indicator, /height\s*:\s*24px/i);
  assert.match(indicator, /top\s*:\s*50%/i);
  assert.match(indicator, /transform\s*:\s*translateY\(-50%\)/i);
  assert.match(indicator, /border-radius\s*:\s*999px/i);
  assert.match(indicator, /background\s*:\s*#5665f4/i);
  assert.match(indicator, /pointer-events\s*:\s*none/i);
});
