import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const shell = fs.readFileSync(new URL("../src/components/AppShell.jsx", import.meta.url), "utf8");
const floatingNav = fs.readFileSync(new URL("../src/components/FloatingNav/FloatingNav.jsx", import.meta.url), "utf8");
const floatingLayout = fs.readFileSync(new URL("../src/styles/floating-layout.css", import.meta.url), "utf8");

test("floating dock keeps route labels stable without the legacy expansion implementation", () => {
  assert.match(shell, /FloatingNav/);
  assert.doesNotMatch(shell, /sidebar|mobileOpen|sidebarRef/);
  assert.doesNotMatch(floatingNav, /from ["']gsap["']/);
  assert.doesNotMatch(floatingNav, /mouseenter|mouseleave|focusin|focusout/);
  assert.doesNotMatch(floatingNav, /timeline|measureExpandedWidth|getFloatingNavWidth/);
  assert.match(floatingNav, /className="floating-nav-label"/);
  assert.doesNotMatch(floatingLayout, /\.floating-nav:hover\s*\{/);
  assert.match(floatingLayout, /\.floating-nav-label[^}]*max-width:\s*none[^}]*opacity:\s*1/s);
  assert.match(floatingLayout, /@media \(max-width: 1439px\)[\s\S]*\.floating-nav-label[^}]*display:\s*none/);
  assert.match(floatingNav, /<div className="floating-nav floating-nav--primary"/);
  assert.match(floatingNav, /<GlassSurface/);
  assert.doesNotMatch(floatingNav, /data-contrast|<LiquidMetalNav|staticControls/);
});
