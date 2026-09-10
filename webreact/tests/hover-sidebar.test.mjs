import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const shell = fs.readFileSync(new URL("../src/components/AppShell.jsx", import.meta.url), "utf8");
const floatingNav = fs.readFileSync(new URL("../src/components/FloatingNav/FloatingNav.jsx", import.meta.url), "utf8");
const floatingLayout = fs.readFileSync(new URL("../src/styles/floating-layout.css", import.meta.url), "utf8");

test("floating dock reveals route labels on desktop without restoring the legacy GSAP implementation", () => {
  assert.match(shell, /FloatingNav/);
  assert.doesNotMatch(shell, /sidebar|mobileOpen|sidebarRef/);
  assert.doesNotMatch(floatingNav, /from ["']gsap["']/);
  assert.doesNotMatch(floatingNav, /mouseenter|mouseleave|focusin|focusout/);
  assert.doesNotMatch(floatingNav, /timeline|measureExpandedWidth|getFloatingNavWidth/);
  assert.match(floatingNav, /className="floating-nav-label"/);
  assert.match(floatingLayout, /\.floating-nav:hover\s*\{/);
  assert.match(floatingLayout, /\.floating-nav:hover[\s\S]*\.floating-nav-label/);
  assert.doesNotMatch(floatingLayout, /\.floating-nav:is\(:hover,\s*:focus-within\)/);
  assert.match(floatingLayout, /@media \(max-width: 760px\)[\s\S]*\.floating-nav-label[^}]*display:\s*none/);
  assert.match(floatingNav, /<Glass[^>]*material="clear"[^>]*interactive/);
  assert.match(floatingNav, /<LiquidMetalNav/);
});
