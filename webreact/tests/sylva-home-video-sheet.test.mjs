import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const webRoot = new URL("../", import.meta.url);

test("the rising sheet reuses the login RippleDistortion as its video background", async () => {
  const homeSource = await readFile(new URL("src/pages/HomePage.jsx", webRoot), "utf8");

  assert.match(homeSource, /import\s+RippleDistortion\s+from\s+["']\.\.\/components\/RippleDistortion\.jsx["']/);
  assert.match(homeSource, /src=["']\/assets\/login-campus\.mp4["']/);
  assert.match(homeSource, /rising-sheet-video/);
  assert.match(homeSource, /className=["']rising-sheet-video["'][\s\S]*?<RippleDistortion/);
});

test("the rising sheet drops the legacy iridescence and glass overlays from JSX", async () => {
  const homeSource = await readFile(new URL("src/pages/HomePage.jsx", webRoot), "utf8");

  assert.doesNotMatch(homeSource, /rising-sheet-iridescence/);
  assert.doesNotMatch(homeSource, /rising-sheet-glass/);
  assert.doesNotMatch(homeSource, /<Iridescence/);
});

test("the rising sheet removes the legacy glass opacity GSAP tween", async () => {
  const homeSource = await readFile(new URL("src/pages/HomePage.jsx", webRoot), "utf8");

  assert.doesNotMatch(homeSource, /querySelector\(["']\.rising-sheet-glass["']\)/);
  assert.doesNotMatch(homeSource, /\.rising-sheet-glass/);
});

test("opening the rising sheet never auto-snaps to the full viewport", async () => {
  const homeSource = await readFile(new URL("src/pages/HomePage.jsx", webRoot), "utf8");

  assert.doesNotMatch(homeSource, /snapTo/);
  assert.doesNotMatch(homeSource, /\bsnap\s*:/);
  assert.doesNotMatch(homeSource, /computeTargetScrollY/);
  assert.doesNotMatch(homeSource, /scrollTo\(\s*\{\s*top:\s*\d{3,}\s*\}/);
});

test("reduced motion skips the home scroll animation", async () => {
  const homeSource = await readFile(new URL("src/pages/HomePage.jsx", webRoot), "utf8");

  assert.match(homeSource, /prefers-reduced-motion/);
  assert.match(homeSource, /reducedMotion/);
});

test("the rising sheet video background covers the entire sheet and stays click-through", async () => {
  const sylvaStyles = await readFile(new URL("src/styles/sylva-home.css", webRoot), "utf8");

  assert.match(sylvaStyles, /\.rising-sheet-video\s*\{[\s\S]*?position:\s*absolute/);
  assert.match(sylvaStyles, /\.rising-sheet-video\s*\{[\s\S]*?inset:\s*0/);
  assert.match(sylvaStyles, /\.rising-sheet-video\s*\{[\s\S]*?pointer-events:\s*none/);
});

test("the rising sheet content stays above the video background layer", async () => {
  const sylvaStyles = await readFile(new URL("src/styles/sylva-home.css", webRoot), "utf8");

  assert.match(sylvaStyles, /\.rising-sheet-content\s*\{[\s\S]*?z-index:\s*[3-9]/);
  assert.match(sylvaStyles, /\.rising-sheet-video\s*\{[\s\S]*?z-index:\s*[01]/);
});

test("the rising sheet no longer paints the large white glass overlay", async () => {
  const sylvaStyles = await readFile(new URL("src/styles/sylva-home.css", webRoot), "utf8");

  assert.doesNotMatch(sylvaStyles, /\.rising-sheet-glass\s*\{/);
  assert.doesNotMatch(sylvaStyles, /\.rising-sheet-iridescence\s*\{/);
});

test("the rising sheet keeps a subtle dark scrim instead of the white glass for readability", async () => {
  const sylvaStyles = await readFile(new URL("src/styles/sylva-home.css", webRoot), "utf8");

  assert.match(sylvaStyles, /\.rising-sheet-scrim/);
  assert.match(sylvaStyles, /\.rising-sheet-scrim\s*\{[\s\S]*?pointer-events:\s*none/);
});

test("the rising sheet keeps playing its video and ripple effect while it is being opened", async () => {
  const homeSource = await readFile(new URL("src/pages/HomePage.jsx", webRoot), "utf8");
  const rippleSource = await readFile(new URL("src/components/RippleDistortion.jsx", webRoot), "utf8");

  assert.match(homeSource, /pauseOnScroll=\{false\}/);
  assert.match(rippleSource, /pauseOnScroll\s*=\s*true/);
  assert.match(rippleSource, /const onScroll = \(\) => \{\s*\n\s*if \(!pauseOnScroll\) return;/);
  assert.match(rippleSource, /\[enabled, pauseOnScroll, quality, src\]/);
});

test("the classic dashboard keeps the bottom video band as a short stage", async () => {
  const sylvaStyles = await readFile(new URL("src/styles/sylva-home.css", webRoot), "utf8");
  const stageRule = sylvaStyles.match(/\.sylva-dashboard \.home-footer-fixed-brand\s*\{([^}]*)\}/)?.[1] || "";

  assert.match(stageRule, /--home-brand-stage-height:\s*clamp\(160px,\s*22vh,\s*300px\)/);
});

test("the classic dashboard keeps its own content height instead of filling the viewport", async () => {
  const sylvaStyles = await readFile(new URL("src/styles/sylva-home.css", webRoot), "utf8");

  assert.match(sylvaStyles, /\.sylva-dashboard:has\(\.home-footer-fixed-brand\)\s*\{[^}]*min-height:\s*0/);
});
