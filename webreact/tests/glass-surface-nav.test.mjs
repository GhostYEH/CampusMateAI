import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const navSource = await readFile(new URL("../src/components/FloatingNav/FloatingNav.jsx", import.meta.url), "utf8");
const liquidNavSource = await readFile(new URL("../src/components/FloatingNav/LiquidMetalNav.jsx", import.meta.url), "utf8");
const liquidNavStyles = await readFile(new URL("../src/components/FloatingNav/LiquidMetalNav.css", import.meta.url), "utf8");
const layoutStyles = await readFile(new URL("../src/styles/floating-layout.css", import.meta.url), "utf8");

test("floating navigation is hosted by a transparent shell with primary liquid-metal controls", () => {
  assert.doesNotMatch(navSource, /import \{ Glass \} from "open-glass-ui"/);
  assert.match(navSource, /<div className="floating-nav floating-nav--primary"/);
  assert.doesNotMatch(navSource, /LiquidGlassSurface/);
  assert.match(liquidNavSource, /<nav aria-label=\{ariaLabel\}/);
});

test("navigation leaves its shell transparent so each route owns the material", () => {
  assert.match(layoutStyles, /\.floating-nav\s*\{[^}]*background:\s*transparent/s);
  assert.doesNotMatch(layoutStyles, /\.floating-nav\.floating-nav-surface/);
  assert.doesNotMatch(layoutStyles, /data-(?:ogui-tone|contrast)/);
});

test("floating navigation reuses the liquid metal runtime instead of gooey particles", () => {
  assert.match(navSource, /import LiquidMetalNav from "\.\/LiquidMetalNav\.jsx"/);
  assert.match(navSource, /<LiquidMetalNav[\s\S]*items=\{navItems\}/);
  assert.match(liquidNavSource, /LiquidMetalButton|mountLiquidMetal/);
  assert.match(liquidNavSource, /onSelect/);
  assert.doesNotMatch(liquidNavSource, /makeParticles/);
  assert.doesNotMatch(liquidNavSource, /gooey-nav-particle/);
  assert.doesNotMatch(liquidNavSource, /gooey-nav-point/);
  assert.doesNotMatch(liquidNavSource, /gooey-nav-effect/);
});

test("navigation no longer ships gooey particle keyframes or styles", () => {
  assert.doesNotMatch(liquidNavStyles, /gooey-nav-particle/);
  assert.doesNotMatch(liquidNavStyles, /gooey-nav-point/);
  assert.doesNotMatch(liquidNavStyles, /gooey-nav-effect/);
  assert.doesNotMatch(liquidNavStyles, /@keyframes\s+gooey-particle/);
  assert.doesNotMatch(liquidNavStyles, /@keyframes\s+gooey-point/);
});

test("stable desktop controls remain unclipped while compact navigation can scroll", () => {
  assert.match(layoutStyles, /\.floating-nav\s*\{[^}]*overflow:\s*visible;/s);
  assert.match(layoutStyles, /@media \(max-width: 1399px\)[\s\S]*\.floating-nav\s*\{[\s\S]*overflow-x:\s*auto;/);
  assert.doesNotMatch(layoutStyles, /\.floating-nav:hover\s*\{/);
});
