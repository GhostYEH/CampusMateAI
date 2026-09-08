import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { navItems } from "../src/components/FloatingNav/navItems.js";

const layoutStyles = readFileSync(new URL("../src/styles/floating-layout.css", import.meta.url), "utf8");
const gooeyStyles = readFileSync(new URL("../src/components/FloatingNav/GooeyNav.css", import.meta.url), "utf8");
const floatingNavSource = readFileSync(new URL("../src/components/FloatingNav/FloatingNav.jsx", import.meta.url), "utf8");
const appShell = readFileSync(new URL("../src/components/AppShell.jsx", import.meta.url), "utf8");

test("adaptive navigation exposes a data-contrast state with light and dark tokens", () => {
  assert.match(floatingNavSource, /data-contrast/);
  assert.match(floatingNavSource, /setAttribute\("data-contrast"/);
  assert.match(floatingNavSource, /"light"|"dark"/);
  assert.match(layoutStyles, /\.floating-nav\[data-contrast="light"\]/);
  assert.match(layoutStyles, /\.floating-nav\[data-contrast="dark"\]/);
});

test("adaptive navigation samples the Sylva scene on the home page only", () => {
  assert.match(floatingNavSource, /\.sylva-home-hero\.sylva-scene-background iframe/);
  assert.match(floatingNavSource, /querySelector\("#scene"\)/);
  assert.match(floatingNavSource, /readPixels/);
  assert.match(floatingNavSource, /CONTRAST_SAMPLE_MS/);
  assert.match(floatingNavSource, /isHomeScene/);
  assert.match(floatingNavSource, /window\.clearInterval/);
});

test("adaptive navigation falls back to a readable default when the scene cannot be sampled", () => {
  assert.match(floatingNavSource, /setAttribute\("data-contrast", "dark"\)/);
  assert.match(floatingNavSource, /catch/);
});

test("adaptive navigation uses explicit contrast tokens and no mix-blend difference", () => {
  assert.match(layoutStyles, /--floating-nav-foreground/);
  assert.match(layoutStyles, /--floating-nav-active-foreground/);
  assert.match(layoutStyles, /--floating-nav-active-background/);
  assert.match(layoutStyles, /--floating-nav-border/);
  assert.match(layoutStyles, /--floating-nav-shadow/);
  assert.match(layoutStyles, /--floating-nav-label-shadow/);
  assert.doesNotMatch(layoutStyles, /mix-blend-mode:\s*difference/);
  assert.doesNotMatch(gooeyStyles, /mix-blend-mode:\s*difference/);
});

test("navigation uses OpenGlass while preserving the existing eight entries", () => {
  assert.match(floatingNavSource, /import \{ Glass \} from ["']open-glass-ui["']/);
  assert.match(floatingNavSource, /<Glass[\s\S]*material="clear"[\s\S]*tone=\{tone\}[\s\S]*interactive/);
  assert.doesNotMatch(floatingNavSource, /LiquidGlassSurface/);
  assert.doesNotMatch(layoutStyles, /\.floating-nav\.floating-nav-surface/);
  assert.equal(navItems.length, 8);
});

test("navigation tone follows the page scene instead of the operating-system theme", () => {
  assert.match(appShell, /const topbarGlassTone = isHome \|\| isStudy \|\| dashboardStyle === "gamified" \? "dark" : "light";/);
  assert.match(appShell, /<FloatingNav tone=\{topbarGlassTone\}/);
  assert.match(layoutStyles, /\.floating-nav\[data-ogui-tone="light"\]/);
  assert.match(layoutStyles, /\.floating-nav\[data-ogui-tone="dark"\]/);
});
