import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const webRoot = new URL("../", import.meta.url);

test("homepage forwards pointer movement to the living background and reactive panes", async () => {
  const [heroSource, pageSource, styles, sceneSource] = await Promise.all([
    readFile(new URL("src/components/SylvaHomeHero.jsx", webRoot), "utf8"),
    readFile(new URL("src/pages/HomePage.jsx", webRoot), "utf8"),
    readFile(new URL("src/styles/sylva-home.css", webRoot), "utf8"),
    readFile(new URL("public/landing-pages/inner-green-3d.html", webRoot), "utf8"),
  ]);

  assert.match(heroSource, /requestAnimationFrame/);
  assert.match(heroSource, /postMessage/);
  assert.match(pageSource, /<SylvaHomeHero\s*\/>/);
  assert.match(styles, /\.sylva-cursor-aura\s*\{/);
  assert.match(styles, /\.sylva-cursor-reactive::before\s*\{/);
  assert.match(styles, /prefers-reduced-motion:\s*reduce/);
  assert.match(sceneSource, /campusmate:pointer/);
});
