import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const appShell = await readFile(new URL("../src/components/AppShell.jsx", import.meta.url), "utf8");
const background = await readFile(new URL("../src/components/Iridescence.jsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");
const homeClassicStyles = await readFile(new URL("../src/styles/home-classic.css", import.meta.url), "utf8");
const homeFooter = await readFile(new URL("../src/components/HomeFooter.jsx", import.meta.url), "utf8");
const particleText = await readFile(new URL("../src/components/ParticleText.jsx", import.meta.url), "utf8");

test("app shell renders the iridescence background instead of a remote image layer", () => {
  assert.match(appShell, /import Iridescence from ["']\.\/Iridescence\.jsx["']/);
  assert.match(appShell, /<Iridescence[\s\S]*className=["']app-iridescence["']/);
  assert.doesNotMatch(appShell, /WallpaperBackground|use[A-Z][A-Za-z]+Wallpaper/);
  assert.doesNotMatch(styles, /wallpaper-layer|wallpaper-scrim/);
});

test("iridescence keeps its base class, hides decorative canvas semantics, and supports reduced motion", () => {
  assert.match(background, /className = ""/);
  assert.match(background, /paused = false/);
  assert.match(background, /className=\{`iridescence-container/);
  assert.match(background, /aria-hidden=\{ariaHidden\}/);
  assert.match(background, /paused/);
  assert.match(background, /WEBGL_lose_context/);
});

test("iridescence tracks the cursor above the click-through background layer", () => {
  assert.match(background, /window\.addEventListener\(["']mousemove["'], handleMouseMove\)/);
  assert.match(background, /window\.removeEventListener\(["']mousemove["'], handleMouseMove\)/);
  assert.doesNotMatch(background, /container\.addEventListener\(["']mousemove["'], handleMouseMove\)/);
});

test("the homepage keeps the full-page iridescence visible behind its content", () => {
  assert.match(appShell, /home-background-active/);
  assert.match(appShell, /location\.pathname === ["']\/home["']/);
  assert.match(styles, /\.home-background-active \.app-iridescence::after/);
  assert.match(homeClassicStyles, /\.home-foreground\{/);
});

test("the brand footer keeps its local particle canvas", () => {
  assert.match(homeFooter, /function HomeBrandCanvas\(\)/);
  assert.match(homeFooter, /<ParticleText/);
  assert.match(particleText, /ResizeObserver/);
  assert.match(particleText, /canvas\.addEventListener\("pointermove"/);
  assert.match(particleText, /<canvas ref=\{canvasRef\}/);
  assert.match(styles, /\.home-footer-brand\s*\{/);
});
