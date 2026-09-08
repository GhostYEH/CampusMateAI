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

test("the smart snap target is computed from viewport ratio rather than a fixed pixel offset", async () => {
  const homeSource = await readFile(new URL("src/pages/HomePage.jsx", webRoot), "utf8");

  assert.match(homeSource, /innerHeight/);
  assert.match(homeSource, /0\.4[89]|0\.5[01]/);
  assert.match(homeSource, /matchMedia\(["']\(max-width:\s*760px\)["']\)/);
  assert.match(homeSource, /0\.7/);
  assert.doesNotMatch(homeSource, /scrollTo\(\s*\{\s*top:\s*\d{3,}\s*\}/);
});

test("refreshing ScrollTrigger does not recursively refresh itself", async () => {
  const homeSource = await readFile(new URL("src/pages/HomePage.jsx", webRoot), "utf8");

  assert.doesNotMatch(homeSource, /onRefresh\s*:\s*\(\)\s*=>\s*ScrollTrigger\.refresh\(\)/);
});

test("reduced motion skips the smart snap animation", async () => {
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

test("the footer information surface lets the sheet video remain visible", async () => {
  const sylvaStyles = await readFile(new URL("src/styles/sylva-home.css", webRoot), "utf8");
  const footerBlocks = [...sylvaStyles.matchAll(/\.sylva-dashboard \.home-footer-info\s*\{([^}]*)\}/g)];
  const backgroundBlock = footerBlocks.find((match) => /background:/.test(match[1]));

  assert.ok(backgroundBlock, "expected a Sylva footer background override");
  const alpha = Number(backgroundBlock[1].match(/rgba\([^)]*,\s*([\d.]+)\)/)?.[1]);
  assert.ok(alpha <= 0.4, `footer background alpha ${alpha} hides too much of the video`);
});
