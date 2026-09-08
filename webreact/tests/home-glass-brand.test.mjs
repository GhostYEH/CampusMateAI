import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const styles = await readFile(new URL("../src/styles/home-classic.css", import.meta.url), "utf8");
const baseStyles = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");
const sylvaStyles = await readFile(new URL("../src/styles/sylva-home.css", import.meta.url), "utf8");

test("classic homepage surfaces keep the liquid-glass treatment", () => {
  assert.match(styles, /\/\* Homepage liquid-glass surfaces[\s\S]*\.home-learning-pulse\{[^}]*background:linear-gradient\(/);
  assert.match(styles, /\/\* Homepage liquid-glass surfaces[\s\S]*\.home-learning-pulse\{[^}]*backdrop-filter:none/);
});

test("homepage brand canvas keeps only the particle field without a backdrop", () => {
  assert.match(baseStyles, /\/\* Home footer liquid-glass surfaces \*\/[\s\S]*\.home-footer-info\s*\{[^}]*background:\s*rgba\(/);
  assert.match(baseStyles, /\.home-footer-brand\s*\{[^}]*min-height:\s*clamp\(/);
  assert.match(baseStyles, /\.home-footer-brand > \.particle-text\s*\{[^}]*position:\s*absolute/);
  assert.match(baseStyles, /\.home-footer-brand-caption\s*\{[^}]*position:\s*absolute/);
  assert.match(baseStyles, /\.home-footer-brand\s*\{[^}]*background:\s*transparent/);
  assert.doesNotMatch(baseStyles, /\.home-footer-brand::before/);
  assert.doesNotMatch(baseStyles, /\.home-footer-brand::after/);
  assert.match(baseStyles, /\.home-footer-fixed-brand \.home-brand-underlay \.home-footer-brand\s*\{[^}]*background:\s*transparent/);
  assert.match(baseStyles, /\.home-footer-fixed-brand \.home-brand-underlay \.home-footer-brand > \.particle-text\s*\{[^}]*filter:\s*drop-shadow/);
  assert.match(sylvaStyles, /\.sylva-dashboard \.home-brand-underlay\s*\{[^}]*background:\s*transparent/);
});

test("homepage surfaces render without entrance animations", () => {
  assert.doesNotMatch(sylvaStyles, /sylva-copy-rise/);
  assert.doesNotMatch(sylvaStyles, /sylva-card-arrive/);
  assert.doesNotMatch(sylvaStyles, /animation-delay:\s*330ms/);
});
