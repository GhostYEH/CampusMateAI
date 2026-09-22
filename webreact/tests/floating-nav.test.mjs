import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { navItems } from "../src/components/FloatingNav/navItems.js";

const styles = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
const layoutStyles = readFileSync(new URL("../src/styles/floating-layout.css", import.meta.url), "utf8");
const navStyles = readFileSync(new URL("../src/components/FloatingNav/FloatingNav.css", import.meta.url), "utf8");
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
      { key: "learning-space", label: "学习空间", icon: "PhChalkboardTeacher" },
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

test("floating navigation uses a readable cool-glass palette globally", () => {
  assert.match(navStyles, /\.floating-nav-list[^}]*color: var\(--floating-nav-foreground, #17304f\)/);
  assert.match(layoutStyles, /\.floating-nav[^}]*--floating-nav-foreground:\s*#17304f/);
  assert.match(layoutStyles, /\.floating-nav[^}]*--floating-nav-active-foreground:\s*#073b70/);
  assert.match(navStyles, /\.floating-nav-glass[^}]*linear-gradient/);
  assert.doesNotMatch(layoutStyles, /\.floating-nav\[data-(?:ogui-tone|contrast)=/);
  assert.doesNotMatch(layoutStyles, /html\[data-theme="auto"\] \.floating-nav/);
});

test("counselor uses the same global floating navigation as other routes", () => {
  assert.match(appShell, /const topbarGlassTone = isHome \|\| isStudy \? "dark" : "light";/);
  assert.match(appShell, /<FloatingNav pendingCount=\{pendingCount\}/);
  assert.doesNotMatch(appShell, /<FloatingNav tone=/);
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

test("desktop navigation keeps every route label visible without hover resizing", () => {
  assert.match(layoutStyles, /\.floating-nav-label/);
  assert.match(floatingNavSource, /floating-nav-label/);
  assert.match(layoutStyles, /\.floating-nav\s*\{[^}]*width:\s*max-content/s);
  assert.match(layoutStyles, /\.floating-nav-label\s*\{[^}]*display:\s*block[^}]*max-width:\s*none[^}]*opacity:\s*1/s);
  assert.doesNotMatch(layoutStyles, /\.floating-nav:hover\s*\{/);
  assert.doesNotMatch(layoutStyles, /--floating-nav-(?:collapsed|expanded)-width/);
  assert.match(layoutStyles, /\.floating-nav \.floating-nav-button\s*\{[^}]*gap:\s*5px[^}]*padding:\s*0 9px/s);
  assert.doesNotMatch(floatingNavSource, /staticControls|LiquidMetalNav/);
});

test("centered navigation uses balanced fixed insets", () => {
  assert.match(layoutStyles, /\.floating-nav \.floating-nav-list[^}]*padding:\s*10px 6px/s);
  assert.match(layoutStyles, /\.floating-nav[^}]*left:\s*50vw[^}]*transform:\s*translateX\(-50%\)/s);
});

test("mobile floating navigation keeps its primary controls compact", () => {
  const mobileStyles = layoutStyles.slice(layoutStyles.lastIndexOf("@media (max-width: 1439px)"));

  assert.match(mobileStyles, /\.floating-nav[^}]*height:\s*calc\(var\(--floating-nav-item-size\) \+ 16px\)/s);
});

test("navigation active state preserves home and exposes the current page", () => {
  assert.match(floatingNavSource, /const active = isActive\(key\)/);
  assert.match(floatingNavSource, /className=\{active \? "active" : undefined\}/);
  assert.match(floatingNavSource, /aria-current=\{active \? "page" : undefined\}/);
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

test("global navigation uses semantic buttons inside one glass surface", () => {
  assert.match(floatingNavSource, /<GlassSurface/);
  assert.match(floatingNavSource, /<button[\s\S]*type="button"/);
  assert.doesNotMatch(floatingNavSource, /LiquidMetalButton|LiquidMetalNav/);
});

test("navigation floating layout drops the legacy active background and underline", () => {
  assert.doesNotMatch(layoutStyles, /\.floating-nav-button\.active::after/);
  assert.doesNotMatch(layoutStyles, /\.floating-nav-button\.active[^}]*background/);
  assert.match(navStyles, /\.floating-nav-list > li\.active \.floating-nav-button/);
  assert.match(navStyles, /\.floating-nav-button:hover/);
  assert.doesNotMatch(styles, /\.floating-nav-button:hover[^}]*background/);
});
