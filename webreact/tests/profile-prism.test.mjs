import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const appShell = await readFile(new URL("../src/components/AppShell.jsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles/profile-patch.css", import.meta.url), "utf8");

test("profile hub uses Prism as an ambient background layer", () => {
  assert.match(appShell, /const isProfile = location\.pathname === ["']\/profile["']/);
  assert.match(appShell, /prefers-reduced-motion/);
  assert.match(appShell, /<Prism[\s\S]*className=["']app-profile-prism["']/);
  assert.match(appShell, /<Prism[\s\S]*animationType=["']3drotate["'][\s\S]*paused=\{motionPaused\}/);
  assert.match(styles, /\.app-layout\.profile-mode[\s\S]*background:/);
  assert.match(styles, /\.app-layout\.profile-mode \.app-content[\s\S]*background: transparent/);
  assert.match(styles, /\.campus-redesign\.profile-redesign[\s\S]*background: transparent/);
  assert.doesNotMatch(styles, /\.campus-redesign\.profile-redesign[\s\S]*backdrop-filter:/);
});
