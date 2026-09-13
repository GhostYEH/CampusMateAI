import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { navItems } from "../src/components/FloatingNav/navItems.js";

const layoutStyles = readFileSync(new URL("../src/styles/floating-layout.css", import.meta.url), "utf8");
const navStyles = readFileSync(new URL("../src/components/FloatingNav/LiquidMetalNav.css", import.meta.url), "utf8");
const floatingNavSource = readFileSync(new URL("../src/components/FloatingNav/FloatingNav.jsx", import.meta.url), "utf8");
const appShell = readFileSync(new URL("../src/components/AppShell.jsx", import.meta.url), "utf8");

test("adaptive navigation exposes a data-contrast state with light and dark tokens", () => {
  assert.match(floatingNavSource, /data-contrast/);
  assert.match(floatingNavSource, /setAttribute\("data-contrast"/);
  assert.match(floatingNavSource, /"light"|"dark"/);
  assert.match(layoutStyles, /\.floating-nav\[data-contrast="light"\]/);
  assert.match(layoutStyles, /\.floating-nav\[data-contrast="dark"\]/);
});

test("adaptive navigation uses a fixed readable home treatment without GPU polling", () => {
  assert.match(floatingNavSource, /isHomeScene/);
  assert.match(floatingNavSource, /setAttribute\("data-contrast", "dark"\)/);
  assert.doesNotMatch(floatingNavSource, /setInterval/);
  assert.doesNotMatch(floatingNavSource, /readPixels/);
});

test("adaptive navigation sets a readable default without requiring scene sampling", () => {
  assert.match(floatingNavSource, /setAttribute\("data-contrast", "dark"\)/);
  assert.doesNotMatch(floatingNavSource, /contentDocument/);
});

test("adaptive navigation uses explicit contrast tokens and no mix-blend difference", () => {
  assert.match(layoutStyles, /--floating-nav-foreground/);
  assert.match(layoutStyles, /--floating-nav-active-foreground/);
  assert.doesNotMatch(layoutStyles, /mix-blend-mode:\s*difference/);
  assert.doesNotMatch(navStyles, /mix-blend-mode:\s*difference/);
});

test("navigation uses OpenGlass while preserving the product entries", () => {
  assert.match(floatingNavSource, /import \{ Glass \} from ["']open-glass-ui["']/);
  assert.match(floatingNavSource, /<Glass[\s\S]*material="clear"[\s\S]*tone=\{tone\}[\s\S]*interactive/);
  assert.doesNotMatch(floatingNavSource, /LiquidGlassSurface/);
  assert.doesNotMatch(layoutStyles, /\.floating-nav\.floating-nav-surface/);
  assert.equal(navItems.length, 9);
});

test("navigation tone follows the page scene instead of the operating-system theme", () => {
  assert.match(appShell, /const topbarGlassTone = isHome \|\| isStudy \|\| dashboardStyle === "gamified" \? "dark" : "light";/);
  assert.match(appShell, /<FloatingNav tone=\{topbarGlassTone\}/);
  assert.match(layoutStyles, /\.floating-nav\[data-ogui-tone="light"\]/);
  assert.match(layoutStyles, /\.floating-nav\[data-ogui-tone="dark"\]/);
});
