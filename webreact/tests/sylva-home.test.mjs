import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";

const webRoot = new URL("../", import.meta.url);

const requiredAssets = Object.freeze([
  ["public/landing-pages/inner-green-assets/three.min.js", "8a5f7249903b54d30f79f708699d2fed2d6a1d0741a4cd41377d1f01bb5a2271"],
  ["public/landing-pages/inner-green-assets/card-ecostove.jpg", "70ce084084902bc502f00c366405b661ecdff90dee95d363b36a6e146829e433"],
  ["public/landing-pages/inner-green-assets/card-ethos.jpg", "337627390f499b3ae272cec9e2f83c817694a82f42e1aa10a7b26a2c7d679dff"],
  ["public/landing-pages/inner-green-assets/lexend-latin.woff2", "1ec8f6ee2750554b4bc59ff0b507d316a82a7ba37e0e5bebc41d3bd9b9faad46"],
]);

test("Sylva homepage keeps every registered runtime asset byte-exact", async () => {
  for (const [path, expectedHash] of requiredAssets) {
    const contents = await readFile(new URL(path, webRoot));
    assert.equal(createHash("sha256").update(contents).digest("hex"), expectedHash, path);
  }
});

test("homepage keeps the Sylva hero as the fixed living-scene background", async () => {
  const [heroSource, homeSource] = await Promise.all([
    readFile(new URL("src/components/SylvaHomeHero.jsx", webRoot), "utf8"),
    readFile(new URL("src/pages/HomePage.jsx", webRoot), "utf8"),
  ]);

  assert.match(heroSource, /import\s*\{\s*SylvaHero\s*\}\s*from\s*["']@designcodeio\/threeui["']/);
  assert.match(heroSource, /variant=["']living-green["']/);
  assert.match(heroSource, /headingFont=["']lexend["']/);
  assert.match(heroSource, /bodyFont=["']lexend["']/);
  assert.match(heroSource, /headingWeight=["']300["']/);
  assert.match(heroSource, /bodyWeight=["']300["']/);
  assert.match(heroSource, /primaryColor=["']#ffffff["']/);
  assert.match(heroSource, /headingSize=\{63\}/);
  assert.match(heroSource, /bodySize=\{16\.5\}/);
  assert.match(heroSource, /headingLetterSpacing=\{-0\.006\}/);
  assert.match(heroSource, /sylva-scene-background/);
  assert.match(homeSource, /<SylvaHomeHero\s*\/>/);
  assert.match(homeSource, /id=["']campus-dashboard["']/);
  assert.match(homeSource, /<ClassicHome/);
});

test("homepage renders the CampusMate first-screen workbench above the background", async () => {
  const homeSource = await readFile(new URL("src/pages/HomePage.jsx", webRoot), "utf8");
  const overviewSource = await readFile(new URL("src/pages/home/SylvaCampusOverview.jsx", webRoot), "utf8");

  assert.match(homeSource, /<section[^>]*className=["']home-stage["']/);
  assert.match(homeSource, /<SylvaCampusOverview\s+state=\{state\}[^>]*onNavigate=\{handleNavigate\}[^>]*onOpenDue=\{handleOpenDue\}[^>]*\/>/);
  assert.match(homeSource, /SylvaCampusOverview/);
  assert.match(overviewSource, /import SylvaPriorityCard from ["']\.\/SylvaPriorityCard\.jsx["']/);
  assert.match(overviewSource, /import SylvaScheduleCard from ["']\.\/SylvaScheduleCard\.jsx["']/);
  assert.match(overviewSource, /learningCommand/);
  assert.match(overviewSource, /todayCourses/);
  assert.match(overviewSource, /overviewMetrics/);
  assert.match(overviewSource, /todayFocusSeconds/);
  assert.match(overviewSource, /onNavigate/);
  assert.match(overviewSource, /onOpenDue/);
});

test("the first-screen priority and schedule modules use real state fields", async () => {
  const [prioritySource, scheduleSource] = await Promise.all([
    readFile(new URL("src/pages/home/SylvaPriorityCard.jsx", webRoot), "utf8"),
    readFile(new URL("src/pages/home/SylvaScheduleCard.jsx", webRoot), "utf8"),
  ]);

  assert.match(prioritySource, /filteredDueItems/);
  assert.match(prioritySource, /overviewMetrics\.pendingCount/);
  assert.match(prioritySource, /onOpenDue/);
  assert.match(prioritySource, /onNavigate\?\.\(\s*["']\/tasks["']/);
  assert.doesNotMatch(prioritySource, /Canopy|Native species|Explore the work/);

  assert.match(scheduleSource, /scheduleItems|todayCourses/);
  assert.match(scheduleSource, /scheduleLoading/);
  assert.match(scheduleSource, /onNavigate\?\.\(\s*["']\/profile\/academic["']/);
  assert.match(scheduleSource, /今天没有排课|管理我的课表/);
});

test("the dashboard below changes responsibility instead of repeating the first screen", async () => {
  const classicSource = await readFile(new URL("src/pages/home/ClassicHome.jsx", webRoot), "utf8");
  const overviewSource = await readFile(new URL("src/pages/home/SylvaCampusOverview.jsx", webRoot), "utf8");

  // The pulse moves into the first-screen workbench and the redundant lower
  // command, schedule, and services blocks stay removed.
  assert.match(overviewSource, /HomeLearningPulse/);
  assert.match(overviewSource, /<HomeLearningPulse\s+items=\{command\.pulse\}/);
  assert.doesNotMatch(classicSource, /HomeLearningPulse/);
  assert.doesNotMatch(classicSource, /simple-priority-panel/);
  assert.doesNotMatch(classicSource, /HomeLearningCommand|HomeSchedulePanel|simple-home-command-stack|simple-home-grid|simple-quick-section/);
  assert.match(classicSource, /<HomeFooter fixedBrand>/);
});

test("the first-screen workbench uses four desktop columns and larger side cards", async () => {
  const sylvaStyles = await readFile(new URL("src/styles/sylva-home.css", webRoot), "utf8");

  assert.match(sylvaStyles, /grid-template-columns:\s*minmax\(280px,\s*1fr\)\s+minmax\(480px,\s*1\.25fr\)\s+minmax\(300px,\s*1fr\)\s+minmax\(300px,\s*1fr\)/);
  assert.match(sylvaStyles, /\.sylva-priority-card[\s\S]*?min-height:\s*390px/);
  assert.match(sylvaStyles, /\.sylva-schedule-card[\s\S]*?min-height:\s*390px/);
  assert.match(sylvaStyles, /\.sylva-overview-pulse/);
});

test("the Sylva scene hides its editorial layer and keeps only the living scene", async () => {
  const sceneSource = await readFile(new URL("public/landing-pages/inner-green-3d.html", webRoot), "utf8");

  assert.match(sceneSource, /html\.bg-only/);
  assert.match(sceneSource, /\.headline/);
  assert.match(sceneSource, /\.card/);
  assert.match(sceneSource, /\.stat/);
  assert.doesNotMatch(sceneSource, /<div class="dock-wrap">/);
  assert.doesNotMatch(sceneSource, /initDock\(\);/);
});

test("the fixed background layer does not move or transform with scroll", async () => {
  const sylvaStyles = await readFile(new URL("src/styles/sylva-home.css", webRoot), "utf8");

  assert.match(sylvaStyles, /\.sylva-home-hero\.sylva-scene-background\s*,[^}]*\.shader-frame\s*\{[\s\S]*?position:\s*fixed/);
  assert.match(sylvaStyles, /inset:\s*0;/);
  assert.match(sylvaStyles, /100svh/);
  assert.match(sylvaStyles, /pointer-events:\s*none/);
  assert.doesNotMatch(sylvaStyles, /scrollY/);
});

test("global navigation keeps one liquid-metal state system across page scenes", async () => {
  const navStyles = await readFile(new URL("src/styles/floating-layout.css", webRoot), "utf8");
  const studyStyles = await readFile(new URL("src/styles/study-summer.css", webRoot), "utf8");

  assert.match(navStyles, /--floating-nav-foreground:\s*#f7f8f2/);
  assert.match(navStyles, /--floating-nav-active-foreground:\s*#ffffff/);
  assert.match(navStyles, /background:\s*transparent/);
  assert.doesNotMatch(navStyles, /data-(?:ogui-tone|contrast)/);
  assert.doesNotMatch(navStyles, /--floating-nav-active-background/);
  assert.doesNotMatch(navStyles, /rgba\(34,\s*40,\s*31,\s*\.74\)/);
  assert.doesNotMatch(studyStyles, /\.app-layout\.study-mode \.floating-nav\s*\{[^}]*background/);
  assert.doesNotMatch(studyStyles, /\.app-layout\.study-mode \.floating-nav-button/);
});
