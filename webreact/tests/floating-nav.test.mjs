import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { navItems } from "../src/components/FloatingNav/navItems.js";

const styles = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
const layoutStyles = readFileSync(new URL("../src/styles/floating-layout.css", import.meta.url), "utf8");
const navStyles = readFileSync(new URL("../src/components/FloatingNav/LiquidMetalNav.css", import.meta.url), "utf8");
const floatingNavSource = readFileSync(new URL("../src/components/FloatingNav/FloatingNav.jsx", import.meta.url), "utf8");
const appShell = readFileSync(new URL("../src/components/AppShell.jsx", import.meta.url), "utf8");
const counselorStyles = readFileSync(new URL("../src/styles/counselor-reference.css", import.meta.url), "utf8");
const sylvaStyles = readFileSync(new URL("../src/styles/sylva-home.css", import.meta.url), "utf8");

test("floating navigation includes the learner world-model route", () => {
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
      { key: "learning-state", label: "学习模型", icon: "PhBrain" },
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
  assert.match(navStyles, /\.liquid-metal-nav-container nav ul[^}]*color: var\(--floating-nav-foreground/);
  assert.doesNotMatch(navStyles, /mix-blend-mode:\s*difference/);
  assert.match(layoutStyles, /\.floating-nav[^}]*--floating-nav-foreground:/);
  assert.match(layoutStyles, /\.floating-nav\[data-ogui-tone="light"\]/);
  assert.match(layoutStyles, /\.floating-nav\[data-ogui-tone="dark"\]/);
  assert.doesNotMatch(layoutStyles, /html\[data-theme="auto"\] \.floating-nav/);
});

test("counselor uses the same global floating navigation as other routes", () => {
  assert.match(appShell, /const topbarGlassTone = isHome \|\| isStudy \? "dark" : "light";/);
  assert.match(appShell, /<FloatingNav tone=\{topbarGlassTone\}/);
  assert.doesNotMatch(counselorStyles, /\.app-layout\.counselor-mode \.floating-nav\{/);
  assert.doesNotMatch(counselorStyles, /\.app-layout\.counselor-mode \.floating-nav-list\{/);
  assert.doesNotMatch(counselorStyles, /\.app-layout\.counselor-mode \.floating-nav-button\{/);
});

test("topbar side controls keep the global search and profile implementation", () => {
  assert.match(appShell, /import LiquidMetalSurface from ["']\.\/LiquidMetalSurface\.jsx["']/);
  assert.match(appShell, /<LiquidMetalSurface[\s\S]*className="topbar-search-surface"/);
  assert.match(appShell, /<SearchField[\s\S]*name="global-search"/);
  assert.match(appShell, /<LiquidMetalSurface[\s\S]*className="topbar-info-surface"/);
  assert.match(appShell, /<IconButton[\s\S]*aria-label="通知"/);
  assert.match(appShell, /<Avatar[\s\S]*name=\{displayName\}/);
  assert.match(appShell, /<div className="topbar-info">[\s\S]*<span className="topbar-date">/);
  assert.match(appShell, /<div className="topbar-actions">/);
  assert.match(styles, /\.topbar-search-surface[^}]*position:\s*fixed/);
  assert.match(styles, /\.topbar-info-surface[^}]*position:\s*fixed/);
});

test("counselor shares the global OpenGlass topbar wrappers", () => {
  assert.match(appShell, /function SearchBox\(\{ tone, disableEffects = false \}\)/);
  assert.match(appShell, /<SearchBox tone=\{topbarGlassTone\} disableEffects=\{motionPaused\} \/>/);
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
  assert.match(styles, /\.topbar-search-surface[^}]*height:\s*var\(--topbar-control-height\)/);
  assert.match(styles, /\.topbar-info-surface[^}]*height:\s*var\(--topbar-control-height\)/);
  assert.match(layoutStyles, /\.floating-nav[^}]*min-height:\s*var\(--topbar-control-height\)/);
  assert.match(styles, /\.topbar-search-surface[^}]*top:\s*14px/);
  assert.match(layoutStyles, /\.floating-nav[^}]*top:\s*14px/);
  assert.match(styles, /\.topbar-info-surface[^}]*top:\s*14px/);
});

test("navigation starts compact and reveals accessible route labels on desktop hover", () => {
  assert.match(layoutStyles, /--floating-nav-expanded-width:\s*900px/);
  assert.match(layoutStyles, /\.floating-nav-label/);
  assert.match(floatingNavSource, /floating-nav-label/);
  assert.match(layoutStyles, /--floating-nav-collapsed-width:\s*424px/);
  assert.match(layoutStyles, /\.floating-nav:hover\s*\{/);
  assert.doesNotMatch(layoutStyles, /\.floating-nav:is\(:hover,\s*:focus-within\)/);
});

test("centered navigation balances the first icon and final profile edge insets", () => {
  assert.match(layoutStyles, /--floating-nav-list-start-padding:\s*8px/);
  assert.match(layoutStyles, /--floating-nav-list-end-padding:\s*8px/);
  assert.match(layoutStyles, /\.floating-nav-list[^}]*padding:\s*8px var\(--floating-nav-list-end-padding\) 8px var\(--floating-nav-list-start-padding\)/s);
  assert.match(layoutStyles, /\.floating-nav[^}]*left:\s*50%[^}]*transform:\s*translateX\(-50%\)/s);
});

test("mobile floating navigation keeps its glass surface compact", () => {
  const mobileStyles = layoutStyles.slice(layoutStyles.lastIndexOf("@media (max-width: 760px)"));

  assert.match(mobileStyles, /\.floating-nav[^}]*height:\s*calc\(var\(--floating-nav-item-size\) \+ 16px\)/s);
});

test("navigation active state uses explicit index comparison so home route stays selected", () => {
  const navSource = readFileSync(new URL("../src/components/FloatingNav/LiquidMetalNav.jsx", import.meta.url), "utf8");
  assert.doesNotMatch(floatingNavSource, /activeIndex\s*\?/);
  assert.doesNotMatch(navSource, /activeIndex\s*\?/);
  assert.match(navSource, /activeIndex === index/);
  assert.match(navSource, /aria-current=\{active\s*\?\s*"page"\s*:\s*undefined\}/);
});

test("navigation removes legacy gooey particle implementation entirely", () => {
  const navSource = readFileSync(new URL("../src/components/FloatingNav/LiquidMetalNav.jsx", import.meta.url), "utf8");
  assert.doesNotMatch(navSource, /makeParticles/);
  assert.doesNotMatch(navSource, /getXY/);
  assert.doesNotMatch(navSource, /gooey-nav-particle/);
  assert.doesNotMatch(navSource, /gooey-nav-point/);
  assert.doesNotMatch(navSource, /gooey-nav-effect/);
  assert.doesNotMatch(navSource, /filterRef/);
  assert.doesNotMatch(navSource, /textRef/);
  assert.doesNotMatch(navStyles, /gooey-nav-particle/);
  assert.doesNotMatch(navStyles, /gooey-nav-point/);
  assert.doesNotMatch(navStyles, /gooey-nav-effect/);
  assert.doesNotMatch(navStyles, /@keyframes\s+gooey-particle/);
  assert.doesNotMatch(navStyles, /@keyframes\s+gooey-point/);
});

test("navigation reuses the liquid metal button for selected and hover states", () => {
  const navSource = readFileSync(new URL("../src/components/FloatingNav/LiquidMetalNav.jsx", import.meta.url), "utf8");
  assert.match(navSource, /LiquidMetalButton/);
  assert.match(navSource, /variant="nav"/);
  assert.match(navSource, /active=\{active\}/);
  assert.match(navSource, /defer/);
});

test("navigation floating layout drops the legacy active background and underline", () => {
  assert.doesNotMatch(layoutStyles, /\.floating-nav-button\.active::after/);
  assert.doesNotMatch(layoutStyles, /\.floating-nav-button\.active[^}]*background/);
  assert.doesNotMatch(layoutStyles, /\.floating-nav-button:hover[^}]*background/);
  assert.doesNotMatch(styles, /\.floating-nav-button:hover[^}]*background/);
});
