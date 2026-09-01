import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

import {
  createMotionProfile,
  resolveReducedMotion,
} from "../src/motion/motionPolicy.js";

test("motion preference respects app, system, and data-saving signals", () => {
  assert.equal(resolveReducedMotion({}), false);
  assert.equal(resolveReducedMotion({ appReduced: true }), true);
  assert.equal(resolveReducedMotion({ systemReduced: true }), true);
  assert.equal(resolveReducedMotion({ saveData: true }), true);
});

test("reduced motion removes travel and duration while preserving completion", () => {
  const standard = createMotionProfile(false);
  const reduced = createMotionProfile(true);

  assert.ok(standard.route.enter.duration > 0);
  assert.ok(standard.route.enter.y > 0);
  assert.equal(reduced.route.enter.duration, 0);
  assert.equal(reduced.route.enter.y, 0);
  assert.equal(reduced.reveal.duration, 0);
  assert.equal(reduced.reveal.y, 0);
});

test("authenticated motion is lifecycle-scoped and canvas rendering uses the GSAP ticker", async () => {
  const [shell, pageMotion, brand] = await Promise.all([
    readFile(new URL("../src/views/AppShell.vue", import.meta.url), "utf8"),
    readFile(new URL("../src/composables/usePageMotion.js", import.meta.url), "utf8"),
    readFile(new URL("../src/components/home/footer/InteractiveBrand.vue", import.meta.url), "utf8"),
  ]);

  assert.match(shell, /:css="false"/);
  assert.match(shell, /animateRouteEnter/);
  assert.match(shell, /animateRouteLeave/);
  assert.match(pageMotion, /gsap\.context/);
  assert.match(pageMotion, /context\.add\("revealBatch"/);
  assert.match(pageMotion, /ScrollTrigger\.batch/);
  assert.match(pageMotion, /start:\s*"top 88%"/);
  assert.match(pageMotion, /ctx\?\.revert\(\)/);
  assert.match(brand, /gsap\.ticker\.add/);
  assert.match(brand, /gsap\.ticker\.remove/);
  assert.doesNotMatch(brand, /requestAnimationFrame/);
});

test("home and study pages opt into ready-gated motion choreography", async () => {
  const [home, study] = await Promise.all([
    readFile(new URL("../src/views/student/StudentHomeView.vue", import.meta.url), "utf8"),
    readFile(new URL("../src/views/student/StudentStudyView.vue", import.meta.url), "utf8"),
  ]);

  for (const source of [home, study]) {
    assert.match(source, /usePageMotion/);
    assert.match(source, /ref="motionRoot"/);
    assert.match(source, /data-motion-reveal/);
  }
  assert.match(home, /parallax:\s*"\.focus-hero-image"/);
  assert.match(study, /parallax:\s*"\.focus-reference-art"/);
});

test("the GSAP route transition is the single page-entry orchestrator", async () => {
  const [styles, ...views] = await Promise.all([
    readFile(new URL("../src/styles.css", import.meta.url), "utf8"),
    readFile(new URL("../src/views/student/StudentCoursesView.vue", import.meta.url), "utf8"),
    readFile(new URL("../src/views/student/StudentTasksView.vue", import.meta.url), "utf8"),
    readFile(new URL("../src/views/student/StudentProfileView.vue", import.meta.url), "utf8"),
  ]);

  assert.doesNotMatch(styles, /\.page-enter\s*\{\s*animation:/);
  views.forEach((source) => assert.doesNotMatch(source, /\bpage-enter\b/));
});
