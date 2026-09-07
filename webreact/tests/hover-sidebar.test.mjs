import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const shell = fs.readFileSync(new URL("../src/components/AppShell.jsx", import.meta.url), "utf8");
const floatingNav = fs.readFileSync(new URL("../src/components/FloatingNav/FloatingNav.jsx", import.meta.url), "utf8");
const styles = fs.readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
const packageJson = JSON.parse(fs.readFileSync(new URL("../package.json", import.meta.url), "utf8"));

test("floating dock is collapsed by default and expands as one unit with GSAP", () => {
  assert.match(shell, /FloatingNav/);
  assert.doesNotMatch(shell, /sidebar|mobileOpen|sidebarRef/);
  assert.match(floatingNav, /mouseenter/);
  assert.match(floatingNav, /mouseleave/);
  assert.match(floatingNav, /gsap\.context/);
  assert.match(floatingNav, /ctx\.revert/);
  assert.equal(typeof packageJson.dependencies.gsap, "string");
  assert.match(floatingNav, /timeline[\s\S]*\.to\(dock, \{ width:/);
  assert.match(floatingNav, /\.to\(buttons, \{ width:/);
  assert.match(styles, /\.floating-nav[^}]*backdrop-filter:\s*blur/);
  assert.doesNotMatch(styles, /transition:\s*width/);
});
