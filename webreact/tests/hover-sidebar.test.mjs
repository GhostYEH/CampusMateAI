import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const shell = fs.readFileSync(new URL("../src/components/AppShell.jsx", import.meta.url), "utf8");
const floatingNav = fs.readFileSync(new URL("../src/components/FloatingNav/FloatingNav.jsx", import.meta.url), "utf8");
const gooeyNav = fs.readFileSync(new URL("../src/components/FloatingNav/GooeyNav.jsx", import.meta.url), "utf8");
const layoutStyles = fs.readFileSync(new URL("../src/styles/floating-layout.css", import.meta.url), "utf8");
const styles = fs.readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");

test("floating dock uses the Sylva proximity and specular interaction without a duplicate expansion mode", () => {
  assert.match(shell, /FloatingNav/);
  assert.doesNotMatch(shell, /sidebar|mobileOpen|sidebarRef/);
  assert.doesNotMatch(floatingNav, /gsap|mouseenter|mouseleave|timeline/);
  assert.match(gooeyNav, /useSpring/);
  assert.match(gooeyNav, /onPointerMove/);
  assert.match(gooeyNav, /--spec-bright/);
  assert.match(layoutStyles, /conic-gradient\(from var\(--spec-angle\)/);
  assert.match(layoutStyles, /backdrop-filter:\s*none/);
  assert.match(styles, /\.floating-nav[^}]*backdrop-filter:\s*blur/);
});
