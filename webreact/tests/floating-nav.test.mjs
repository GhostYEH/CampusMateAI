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
const sylvaStyles = readFileSync(new URL("../src/styles/sylva-home.css", import.meta.url), "utf8");

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
  assert.match(layoutStyles, /\.floating-nav\[data-ogui-tone="light"\]/);
  assert.match(layoutStyles, /\.floating-nav\[data-ogui-tone="dark"\]/);
  assert.doesNotMatch(layoutStyles, /html\[data-theme="auto"\] \.floating-nav/);
});

test("counselor uses the same global floating navigation as other routes", () => {
  assert.match(appShell, /const topbarGlassTone = isHome \|\| isStudy \|\| dashboardStyle === "gamified" \? "dark" : "light";/);
  assert.match(appShell, /<FloatingNav tone=\{topbarGlassTone\}/);
  assert.doesNotMatch(counselorStyles, /\.app-layout\.counselor-mode \.floating-nav\{/);
  assert.doesNotMatch(counselorStyles, /\.app-layout\.counselor-mode \.floating-nav-list\{/);
  assert.doesNotMatch(counselorStyles, /\.app-layout\.counselor-mode \.floating-nav-button\{/);
});

test("topbar side controls keep the global search and profile implementation", () => {
  assert.match(appShell, /import \{ Avatar, Glass, IconButton, SearchField \} from "open-glass-ui"/);
  assert.match(appShell, /<Glass[\s\S]*className="topbar-search-surface"/);
  assert.match(appShell, /<SearchField[\s\S]*name="global-search"/);
  assert.match(appShell, /<Glass[\s\S]*className="topbar-info-surface"/);
  assert.match(appShell, /<IconButton[\s\S]*aria-label="通知"/);
  assert.match(appShell, /<Avatar[\s\S]*name=\{displayName\}/);
  assert.match(appShell, /<div className="topbar-info">[\s\S]*<span className="topbar-date">/);
  assert.match(appShell, /<div className="topbar-actions">/);
  assert.match(styles, /\.topbar-search-surface[^}]*position:\s*fixed/);
  assert.match(styles, /\.topbar-info-surface[^}]*position:\s*fixed/);
});

test("counselor shares the global OpenGlass topbar wrappers", () => {
  assert.match(appShell, /function SearchBox\(\{ tone \}\)/);
  assert.match(appShell, /<SearchBox tone=\{topbarGlassTone\} \/>/);
  assert.match(appShell, /topbar-search-surface/);
  assert.match(appShell, /topbar-info-surface/);
});

test("Sylva home keeps the shared side controls and navigation baseline", () => {
  assert.doesNotMatch(sylvaStyles, /\.app-layout:has\(\.sylva-home-page\) \.topbar > :not\(\.floating-nav\)\s*\{\s*display:\s*none/);
  assert.doesNotMatch(sylvaStyles, /\.app-layout:has\(\.sylva-home-page\) \.floating-nav\s*\{\s*top:\s*clamp\(/);
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

  assert.match(mobileStyles, /\.floating-nav[^}]*height:\s*calc\(var\(--floating-nav-item-size\) \+ 16px\)/s);
});

test("navigation active state uses explicit index comparison so home route stays selected", () => {
  const gooeySource = readFileSync(new URL("../src/components/FloatingNav/GooeyNav.jsx", import.meta.url), "utf8");
  assert.doesNotMatch(floatingNavSource, /activeIndex\s*\?/);
  assert.doesNotMatch(gooeySource, /activeIndex\s*\?/);
  assert.match(gooeySource, /activeIndex === index/);
  assert.match(gooeySource, /aria-current=\{active\s*\?\s*"page"\s*:\s*undefined\}/);
});

test("navigation removes legacy gooey particle implementation entirely", () => {
  const gooeySource = readFileSync(new URL("../src/components/FloatingNav/GooeyNav.jsx", import.meta.url), "utf8");
  assert.doesNotMatch(gooeySource, /makeParticles/);
  assert.doesNotMatch(gooeySource, /getXY/);
  assert.doesNotMatch(gooeySource, /gooey-nav-particle/);
  assert.doesNotMatch(gooeySource, /gooey-nav-point/);
  assert.doesNotMatch(gooeySource, /gooey-nav-effect/);
  assert.doesNotMatch(gooeySource, /filterRef/);
  assert.doesNotMatch(gooeySource, /textRef/);
  assert.doesNotMatch(navStyles, /gooey-nav-particle/);
  assert.doesNotMatch(navStyles, /gooey-nav-point/);
  assert.doesNotMatch(navStyles, /gooey-nav-effect/);
  assert.doesNotMatch(navStyles, /@keyframes\s+gooey-particle/);
  assert.doesNotMatch(navStyles, /@keyframes\s+gooey-point/);
});

test("navigation reuses the liquid metal button for selected and hover states", () => {
  const gooeySource = readFileSync(new URL("../src/components/FloatingNav/GooeyNav.jsx", import.meta.url), "utf8");
  assert.match(gooeySource, /LiquidMetalButton/);
  assert.match(gooeySource, /variant="nav"/);
  assert.match(gooeySource, /active=\{active\}/);
  assert.match(gooeySource, /defer/);
});

test("navigation floating layout drops the legacy active background and underline", () => {
  assert.doesNotMatch(layoutStyles, /\.floating-nav-button\.active::after/);
  assert.doesNotMatch(layoutStyles, /\.floating-nav-button\.active[^}]*background/);
  assert.doesNotMatch(layoutStyles, /\.floating-nav-button:hover[^}]*background/);
});
