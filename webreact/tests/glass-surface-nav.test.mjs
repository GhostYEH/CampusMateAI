import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const navSource = await readFile(new URL("../src/components/FloatingNav/FloatingNav.jsx", import.meta.url), "utf8");
const liquidNavSource = await readFile(new URL("../src/components/FloatingNav/LiquidMetalNav.jsx", import.meta.url), "utf8");
const liquidNavStyles = await readFile(new URL("../src/components/FloatingNav/LiquidMetalNav.css", import.meta.url), "utf8");
const layoutStyles = await readFile(new URL("../src/styles/floating-layout.css", import.meta.url), "utf8");

test("floating navigation is hosted by the OpenGlass surface", () => {
  assert.match(navSource, /import \{ Glass \} from "open-glass-ui"/);
  assert.match(navSource, /<Glass[\s\S]*className=\{`floating-nav floating-nav--\$\{tone\}`\}[\s\S]*material="clear"[\s\S]*tone=\{tone\}[\s\S]*interactive/);
  assert.doesNotMatch(navSource, /LiquidGlassSurface/);
  assert.match(liquidNavSource, /<nav aria-label=\{ariaLabel\}/);
});

test("navigation delegates optical material and accessibility fallbacks to OpenGlass", () => {
  assert.doesNotMatch(layoutStyles, /\.floating-nav\.floating-nav-surface/);
  assert.doesNotMatch(layoutStyles, /liquid glass material \(nav only\)/i);
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

test("desktop hover scaling can render the edge selection marker without clipping", () => {
  assert.match(layoutStyles, /@media \(hover: hover\) and \(pointer: fine\)[\s\S]*\.floating-nav\s*\{[\s\S]*overflow:\s*visible;/);
  assert.match(layoutStyles, /@media \(max-width: 760px\)[\s\S]*\.floating-nav\s*\{[\s\S]*overflow-x:\s*auto;/);
});
