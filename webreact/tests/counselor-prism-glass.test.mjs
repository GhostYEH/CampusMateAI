import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const counselorPage = await readFile(new URL("../src/pages/CounselorPage.jsx", import.meta.url), "utf8");
const appShell = await readFile(new URL("../src/components/AppShell.jsx", import.meta.url), "utf8");
const prism = await readFile(new URL("../src/components/Prism.jsx", import.meta.url), "utf8").catch(() => "");
const ripple = await readFile(new URL("../src/components/RippleDistortion.jsx", import.meta.url), "utf8").catch(() => "");
const styles = await readFile(new URL("../src/styles/counselor-reference.css", import.meta.url), "utf8");

test("counselor page uses a full-height interactive Prism background", () => {
  assert.match(appShell, /import Prism from ["']\.\/Prism\.jsx["']/);
  assert.match(appShell, /<Prism[\s\S]*className=["']app-counselor-prism["']/);
  assert.match(appShell, /animationType=["']3drotate["']/);
  assert.match(appShell, /suspendWhenOffscreen=\{false\}/);
  assert.doesNotMatch(counselorPage, /import Prism from/);
  assert.match(prism, /from ["']ogl["']/);
  assert.match(prism, /requestAnimationFrame/);
  assert.match(prism, /paused = false/);
});

test("counselor hero uses RippleDistortion over the local campus artwork", () => {
  assert.match(counselorPage, /import RippleDistortion from ["']\.\.\/components\/RippleDistortion\.jsx["']/);
  assert.match(counselorPage, /<RippleDistortion[\s\S]*className=["']counselor-ripple["']/);
  assert.match(counselorPage, /src=["']\/assets\/counselor-campus-hero-reference\.png["']/);
  assert.match(counselorPage, /trigger=["']both["']/);
  assert.match(ripple, /from ["']ogl["']/);
  assert.match(ripple, /RenderTarget/);
  assert.match(ripple, /pointermove/);
});

test("counselor layout enlarges the title and uses translucent glass surfaces", () => {
  assert.match(styles, /\.counselor-reference-title h1\{[^}]*font-size:clamp\(\d+px,\s*\d+vw,\s*\d+px\)/);
  assert.match(styles, /\.counselor-reference\{[^}]*max-width:1680px/);
  for (const selector of [
    ".counselor-panel",
    ".reference-composer",
    ".reference-action-row button",
    ".digital-human-controls button",
  ]) {
    assert.ok(styles.includes(selector), selector);
  }
  assert.match(styles, /backdrop-filter:blur\(/);
  assert.match(styles, /background:rgba\(255,255,255,\.\d+\)/);
  assert.match(styles, /\.app-layout\.counselor-mode \.app-content\{[^}]*background:transparent/);
  assert.match(styles, /@media\(prefers-reduced-motion:reduce\)/);
});
