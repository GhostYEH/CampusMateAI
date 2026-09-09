import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const shell = fs.readFileSync(new URL("../src/components/AppShell.jsx", import.meta.url), "utf8");
const floatingNav = fs.readFileSync(new URL("../src/components/FloatingNav/FloatingNav.jsx", import.meta.url), "utf8");
test("floating dock stays compact and does not keep the legacy GSAP expansion", () => {
  assert.match(shell, /FloatingNav/);
  assert.doesNotMatch(shell, /sidebar|mobileOpen|sidebarRef/);
  assert.doesNotMatch(floatingNav, /from ["']gsap["']/);
  assert.doesNotMatch(floatingNav, /mouseenter|mouseleave|focusin|focusout/);
  assert.doesNotMatch(floatingNav, /timeline|measureExpandedWidth|getFloatingNavWidth/);
  assert.doesNotMatch(floatingNav, /floating-nav-label/);
  assert.match(floatingNav, /<Glass[^>]*material="clear"[^>]*interactive/);
  assert.match(floatingNav, /<LiquidMetalNav/);
});
