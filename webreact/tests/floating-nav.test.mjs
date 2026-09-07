import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { navItems } from "../src/components/FloatingNav/navItems.js";

const styles = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
const layoutStyles = readFileSync(new URL("../src/styles/floating-layout.css", import.meta.url), "utf8");
const navStyles = readFileSync(new URL("../src/components/FloatingNav/GooeyNav.css", import.meta.url), "utf8");
const floatingNavSource = readFileSync(new URL("../src/components/FloatingNav/FloatingNav.jsx", import.meta.url), "utf8");
const appShell = readFileSync(new URL("../src/components/AppShell.jsx", import.meta.url), "utf8");
const counselorStyles = readFileSync(new URL("../src/styles/counselor-reference.css", import.meta.url), "utf8");

test("floating navigation keeps the existing eight route entries", () => {
  assert.deepEqual(
    navItems.map(({ key, label, icon }) => ({ key, label, icon })),
    [
      { key: "home", label: "首页", icon: "PhHouse" },
      { key: "courses", label: "我的课程", icon: "PhBookOpen" },
      { key: "community", label: "校园社区", icon: "PhChatsCircle" },
      { key: "tasks", label: "待办与作业", icon: "PhCheckSquare" },
      { key: "counselor", label: "AI 校园助手", icon: "PhRobot" },
      { key: "notifications", label: "通知整理", icon: "PhBell" },
      { key: "study", label: "学习陪伴", icon: "PhChartLineUp" },
      { key: "profile", label: "个人中心", icon: "PhUser" },
    ],
  );
});

test("global search gets a wider desktop field without changing mobile layout", () => {
  assert.match(styles, /\.topbar-search[^}]*width: min\(240px, calc\(100vw - 30px\)\)/);
  assert.match(styles, /\.search-wrap[^}]*width: 240px/);
  const mobileStyles = styles.slice(styles.indexOf("@media (max-width: 760px)"), styles.indexOf("@media (max-width: 390px)"));
  assert.match(mobileStyles, /\.search-wrap[^}]*left: 15px[^}]*width: min\(190px, calc\(100vw - 30px\)\)/);
  assert.match(mobileStyles, /\.topbar-search[^}]*width: min\(190px, calc\(100vw - 30px\)\)/);
  const tinyStyles = styles.slice(styles.indexOf("@media (max-width: 390px)"), styles.indexOf("@media (max-width: 390px)", styles.indexOf("@media (max-width: 390px)") + 1));
  assert.match(tinyStyles, /\.search-wrap[^}]*width: 174px/);
});

test("floating navigation foreground uses explicit contrast tokens", () => {
  assert.match(navStyles, /\.gooey-nav-container nav ul[^}]*color: var\(--floating-nav-foreground/);
  assert.doesNotMatch(navStyles, /mix-blend-mode:\s*difference/);
  assert.match(layoutStyles, /\.floating-nav[^}]*--floating-nav-foreground:/);
  assert.match(layoutStyles, /\.floating-nav--light/);
});

test("counselor uses the same global floating navigation as other routes", () => {
  assert.match(appShell, /const floatingNavTone = isCounselor \|\| dashboardStyle === "gamified" \? "light" : "dark";/);
  assert.match(appShell, /<FloatingNav tone=\{floatingNavTone\}/);
  assert.doesNotMatch(counselorStyles, /\.app-layout\.counselor-mode \.floating-nav\{/);
  assert.doesNotMatch(counselorStyles, /\.app-layout\.counselor-mode \.floating-nav-list\{/);
  assert.doesNotMatch(counselorStyles, /\.app-layout\.counselor-mode \.floating-nav-button\{/);
});

test("topbar side controls keep the global search and profile implementation", () => {
  assert.match(appShell, /import LiquidGlassSurface from "\.\/LiquidGlassSurface\.jsx"/);
  assert.match(appShell, /<LiquidGlassSurface[\s\S]*className="topbar-search-surface"/);
  assert.match(appShell, /<LiquidGlassSurface[\s\S]*className="topbar-info-surface"/);
  assert.match(appShell, /<div className="topbar-info">[\s\S]*<span className="topbar-date">/);
  assert.match(appShell, /<div className="topbar-actions">/);
  assert.match(styles, /\.topbar-search-surface[^}]*position:\s*fixed/);
  assert.match(styles, /\.topbar-info-surface[^}]*position:\s*fixed/);
});

test("counselor shares the global liquid-glass topbar wrappers", () => {
  assert.match(appShell, /function SearchBox\(\)/);
  assert.match(appShell, /<SearchBox \/>/);
  assert.match(appShell, /topbar-search-surface/);
  assert.match(appShell, /topbar-info-surface/);
});

test("active navigation item does not paint a duplicate blue ring", () => {
  assert.doesNotMatch(navStyles, /\.floating-nav-icon::before/);
  assert.doesNotMatch(navStyles, /\.floating-nav-icon::after/);
});

test("topbar controls share one desktop height and top alignment", () => {
  assert.match(styles, /--topbar-control-height:\s*64px/);
  assert.match(styles, /\.topbar-search[^}]*height:\s*var\(--topbar-control-height\)/);
  assert.match(styles, /\.topbar-info[^}]*height:\s*var\(--topbar-control-height\)/);
  assert.match(styles, /\.floating-nav[^}]*min-height:\s*var\(--topbar-control-height\)/);
  assert.match(styles, /\.topbar-search[^}]*top:\s*10px/);
  assert.match(styles, /\.floating-nav[^}]*top:\s*10px|\.floating-nav[^}]*top:\s*14px/);
  assert.match(styles, /\.topbar-info[^}]*top:\s*10px/);
});

test("Sylva navigation keeps compact dock geometry with readable labels", () => {
  assert.match(layoutStyles, /--floating-nav-item-size:\s*36px/);
  assert.match(layoutStyles, /--floating-nav-item-gap:\s*3px/);
  assert.match(layoutStyles, /\.floating-nav-label[^}]*font-size:\s*11px/);
  assert.match(layoutStyles, /\.floating-nav-button[^}]*padding:\s*0 13px/);
});

test("centered navigation fits its eight labels without a second expansion state", () => {
  assert.match(layoutStyles, /--floating-nav-list-start-padding:\s*5px/);
  assert.match(layoutStyles, /--floating-nav-list-end-padding:\s*5px/);
  assert.match(layoutStyles, /\.floating-nav[^}]*width:\s*max-content/);
  assert.doesNotMatch(floatingNavSource, /gsap|timeline|mouseenter/);
  assert.match(styles, /\.floating-nav[^}]*left:\s*50%[^}]*transform:\s*translateX\(-50%\)/s);
});

test("mobile floating navigation keeps its glass surface compact", () => {
  const mobileStyles = layoutStyles.slice(layoutStyles.lastIndexOf("@media (max-width: 760px)"));

  assert.match(mobileStyles, /\.floating-nav[^}]*height:\s*calc\(var\(--floating-nav-item-size\) \+ 12px\)/s);
  assert.match(mobileStyles, /\.floating-nav-label[^}]*display:\s*none/s);
});

test("medium viewports collapse labels before the navigation can overlap side controls", () => {
  const mediumStyles = layoutStyles.slice(layoutStyles.indexOf("@media (max-width: 1200px)"));

  assert.match(mediumStyles, /\.floating-nav-button[^}]*width:\s*var\(--floating-nav-item-size\)/s);
  assert.match(mediumStyles, /\.floating-nav-label[^}]*position:\s*absolute/s);
  assert.match(mediumStyles, /\.floating-nav-list li:hover \.floating-nav-label[^}]*opacity:\s*1/s);
});
