import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const navSource = await readFile(new URL("../src/components/FloatingNav/FloatingNav.jsx", import.meta.url), "utf8");
const glassSource = await readFile(new URL("../src/components/GlassSurface.jsx", import.meta.url), "utf8");
const navStyles = await readFile(new URL("../src/components/FloatingNav/FloatingNav.css", import.meta.url), "utf8");
const layoutStyles = await readFile(new URL("../src/styles/floating-layout.css", import.meta.url), "utf8");

test("floating navigation uses the React Bits glass surface", () => {
  assert.doesNotMatch(navSource, /import \{ Glass \} from "open-glass-ui"/);
  assert.match(navSource, /<div className="floating-nav floating-nav--primary"/);
  assert.match(navSource, /import GlassSurface from "\.\.\/GlassSurface\.jsx"/);
  assert.match(navSource, /<GlassSurface[\s\S]*className="floating-nav-glass"/);
  assert.match(navSource, /<nav className="floating-nav-inner" aria-label="主导航">/);
  assert.match(glassSource, /feDisplacementMap/);
  assert.match(glassSource, /backdropFilter = `url\(#\$\{filterId\}\)`/);
});

test("glass surface forwards semantic attributes to its outer element", () => {
  assert.match(glassSource, /style = \{\},\s*\.\.\.props/);
  assert.match(glassSource, /<div \{\.\.\.props\} ref=\{containerRef\}/);
});

test("navigation shell stays transparent while the glass surface owns the material", () => {
  assert.match(layoutStyles, /\.floating-nav\s*\{[^}]*background:\s*transparent/s);
  assert.match(navStyles, /\.floating-nav-glass\s*\{[\s\S]*linear-gradient/);
  assert.match(navStyles, /backdrop|glass-surface/);
  assert.match(navStyles, /inset 0 1px 0/);
});

test("global navigation removes the previous liquid-metal and dock effects", () => {
  assert.doesNotMatch(navSource, /LiquidMetalNav/);
  assert.doesNotMatch(navSource, /LiquidMetalButton/);
  assert.doesNotMatch(navSource, /motion\/react|useSpring|useMotionValue|getDockScale/);
  assert.doesNotMatch(navSource, /canvas/i);
  assert.match(navSource, /navItems\.map/);
});

test("glass navigation keeps clear active, hover and keyboard focus states", () => {
  assert.match(navStyles, /\.floating-nav-list > li\.active \.floating-nav-button/);
  assert.match(navStyles, /\.floating-nav-button:hover/);
  assert.match(navStyles, /\.floating-nav-button:focus-visible/);
  assert.match(navStyles, /@media \(prefers-reduced-motion: reduce\)/);
});

test("stable desktop controls remain unclipped while compact navigation can scroll", () => {
  assert.match(layoutStyles, /\.floating-nav\s*\{[^}]*overflow:\s*visible;/s);
  assert.match(layoutStyles, /@media \(max-width: 1439px\)[\s\S]*\.floating-nav\s*\{[\s\S]*overflow-x:\s*auto;/);
  assert.match(navStyles, /@media \(max-width: 1439px\)[\s\S]*\.floating-nav-glass > \.glass-surface__content\s*\{[\s\S]*overflow-x:\s*auto;/);
  assert.doesNotMatch(layoutStyles, /\.floating-nav:hover\s*\{/);
});
