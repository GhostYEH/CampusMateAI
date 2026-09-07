import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const navSource = await readFile(new URL("../src/components/FloatingNav/FloatingNav.jsx", import.meta.url), "utf8");
const gooeySource = await readFile(new URL("../src/components/FloatingNav/GooeyNav.jsx", import.meta.url), "utf8");
const gooeyStyles = await readFile(new URL("../src/components/FloatingNav/GooeyNav.css", import.meta.url), "utf8");
const layoutStyles = await readFile(new URL("../src/styles/floating-layout.css", import.meta.url), "utf8");

test("floating navigation is hosted by the OpenGlass surface", () => {
  assert.match(navSource, /import \{ Glass \} from "open-glass-ui"/);
  assert.match(navSource, /<Glass[\s\S]*className=\{`floating-nav floating-nav--\$\{tone\}`\}[\s\S]*material="regular"[\s\S]*interactive/);
  assert.doesNotMatch(navSource, /LiquidGlassSurface/);
  assert.match(gooeySource, /<nav aria-label=\{ariaLabel\}/);
});

test("navigation delegates optical material and accessibility fallbacks to OpenGlass", () => {
  assert.doesNotMatch(layoutStyles, /\.floating-nav\.floating-nav-surface/);
  assert.doesNotMatch(layoutStyles, /liquid glass material \(nav only\)/i);
});

test("floating navigation uses a route-safe gooey click effect in the existing palette", () => {
  assert.match(navSource, /import GooeyNav from "\.\/GooeyNav\.jsx"/);
  assert.match(navSource, /<GooeyNav[\s\S]*items=\{navItems\}/);
  assert.match(gooeySource, /requestAnimationFrame/);
  assert.match(gooeySource, /onSelect/);
  assert.match(gooeyStyles, /--color-1:\s*#3267d6/);
  assert.match(gooeyStyles, /--color-3:\s*#765eea/);
  assert.doesNotMatch(gooeyStyles, /(?:color|background):\s*white\b|#fff\b/i);
});

test("gooey selection backdrop stays transparent so the glass nav is not painted white", () => {
  assert.match(
    gooeyStyles,
    /\.gooey-nav-container \.gooey-nav-effect\.filter::before\s*\{[^}]*background:\s*transparent;/s,
  );
});

test("desktop hover scaling can render the edge selection marker without clipping", () => {
  assert.match(layoutStyles, /@media \(hover: hover\) and \(pointer: fine\)[\s\S]*\.floating-nav\s*\{[\s\S]*overflow:\s*visible;/);
  assert.match(layoutStyles, /@media \(max-width: 760px\)[\s\S]*\.floating-nav\s*\{[\s\S]*overflow-x:\s*auto;/);
});
