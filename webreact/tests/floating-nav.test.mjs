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
  assert.match(styles, /\.topbar-search[^}]*var\(--topbar-glass-background\)/);
  assert.match(styles, /\.topbar-info[^}]*var\(--topbar-glass-background\)/);
  assert.doesNotMatch(appShell, /import GlassSurface from/);
  assert.match(appShell, /<div className="topbar-info">[\s\S]*<span className="topbar-date">/);
  assert.match(appShell, /<div className="topbar-actions">/);
});

test("counselor does not add private topbar wrappers", () => {
  assert.match(appShell, /function SearchBox\(\)/);
  assert.match(appShell, /<SearchBox \/>/);
  assert.doesNotMatch(appShell, /topbar-glass-control|topbar-search-surface|topbar-profile-surface/);
});

test("active navigation item does not paint a duplicate blue ring", () => {
  assert.doesNotMatch(navStyles, /\.floating-nav-icon::before/);
  assert.doesNotMatch(navStyles, /\.floating-nav-icon::after/);
});

test("topbar controls share one desktop height and top alignment", () => {
  assert.match(styles, /--topbar-control-height:\s*64px/);
  assert.match(styles, /\.topbar-search[^}]*height:\s*var\(--topbar-control-height\)/);
  assert.match(styles, /\.topbar-info[^}]*height:\s*var\(--topbar-control-height\)/);
  assert.match(styles, /\.floating-nav\.glass-surface[^}]*min-height:\s*var\(--topbar-control-height\)/);
  assert.match(styles, /\.topbar-search[^}]*top:\s*10px/);
  assert.match(styles, /\.floating-nav[^}]*top:\s*10px/);
  assert.match(styles, /\.topbar-info[^}]*top:\s*10px/);
});

test("expanded navigation reserves more space for larger labels and the profile item", () => {
  assert.match(layoutStyles, /--floating-nav-expanded-button-offset:\s*76px/);
  assert.match(layoutStyles, /--floating-nav-expanded-item-gap:\s*30px/);
  assert.match(layoutStyles, /\.floating-nav-label[^}]*font-size:\s*14px/);
});

test("centered navigation balances the first icon and final profile edge insets", () => {
  assert.match(layoutStyles, /--floating-nav-list-start-padding:\s*8px/);
  assert.match(layoutStyles, /--floating-nav-list-end-padding:\s*30px/);
  assert.match(layoutStyles, /\.floating-nav-list[^}]*padding:\s*8px var\(--floating-nav-list-end-padding\) 8px var\(--floating-nav-list-start-padding\)/s);
  assert.match(floatingNavSource, /listPaddingEnd[\s\S]*contentWidth/);
  assert.match(styles, /\.floating-nav[^}]*left:\s*50%[^}]*transform:\s*translateX\(-50%\)/s);
});

test("mobile floating navigation keeps its glass surface compact", () => {
  const mobileStyles = layoutStyles.slice(layoutStyles.lastIndexOf("@media (max-width: 760px)"));

  assert.match(mobileStyles, /\.floating-nav\.glass-surface[^}]*height:\s*calc\(var\(--floating-nav-item-size\) \+ 16px\)/s);
});
