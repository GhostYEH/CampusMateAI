import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), "utf8");

test("Smooth Cursor is wired into the authenticated shell with motion-safe defaults", () => {
  const component = read("src/components/SmoothCursor.jsx");
  const shell = read("src/components/AppShell.jsx");
  const styles = read("src/styles.css");

  assert.match(component, /requestAnimationFrame/);
  assert.match(component, /springStrength/);
  assert.match(component, /aria-hidden="true"/);
  assert.match(shell, /import SmoothCursor from ["']\.\/SmoothCursor\.jsx["']/);
  assert.match(shell, /<SmoothCursor[\s\S]*motionPaused/);
  assert.match(styles, /\.smooth-cursor-layer[\s\S]*pointer-events:\s*none/);
  assert.match(styles, /\.reduce-motion \.smooth-cursor-layer[\s\S]*display:\s*none/);
  assert.match(styles, /prefers-reduced-motion: reduce[\s\S]*\.smooth-cursor-layer/);
});
