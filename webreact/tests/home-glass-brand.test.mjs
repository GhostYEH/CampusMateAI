import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const styles = await readFile(new URL("../src/styles/home-classic.css", import.meta.url), "utf8");
const baseStyles = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");

test("classic homepage surfaces keep the liquid-glass treatment", () => {
  assert.match(styles, /\/\* Homepage liquid-glass surfaces[\s\S]*\.home-learning-command,.home-learning-pulse,.student-home-panel,.simple-quick-section\{[^}]*background:rgba\(/);
  assert.match(styles, /\/\* Homepage liquid-glass surfaces[\s\S]*\.home-learning-command,.home-learning-pulse,.student-home-panel,.simple-quick-section\{[^}]*backdrop-filter:blur\(/);
});

test("homepage brand canvas has a visible stage instead of collapsing", () => {
  assert.match(baseStyles, /\/\* Home footer liquid-glass surfaces \*\/[\s\S]*\.home-footer-info\s*\{[^}]*background:\s*rgba\(/);
  assert.match(baseStyles, /\.home-footer-brand\s*\{[^}]*min-height:\s*clamp\(/);
  assert.match(baseStyles, /\.home-footer-brand > \.particle-text\s*\{[^}]*position:\s*absolute/);
  assert.match(baseStyles, /\.home-footer-brand-caption\s*\{[^}]*position:\s*absolute/);
  assert.match(baseStyles, /\.home-footer-fixed-brand \.home-brand-underlay \.home-footer-brand\s*\{[^}]*background:\s*transparent/);
  assert.match(baseStyles, /\.home-footer-fixed-brand \.home-brand-underlay \.home-footer-brand::before[\s\S]*display:\s*none/);
  assert.match(baseStyles, /\.home-footer-fixed-brand \.home-brand-underlay \.home-footer-brand > \.particle-text\s*\{[^}]*filter:\s*drop-shadow/);
});
