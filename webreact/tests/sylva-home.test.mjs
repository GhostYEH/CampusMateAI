import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";

const webRoot = new URL("../", import.meta.url);

const requiredAssets = Object.freeze([
  ["public/landing-pages/inner-green-3d.html", "69c3694bd63f44ef9f007ebe4dac57a83e4402e0cdf6b54dd10b96dd4f05e197"],
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

test("homepage opens with the configured Living Green hero before the existing dashboard", async () => {
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
  assert.match(homeSource, /<SylvaHomeHero/);
  assert.match(homeSource, /id=["']campus-dashboard["']/);
  assert.match(homeSource, /<ClassicHome|<GamifiedHome/);
});

test("global navigation carries the authored Living Green glass and paper states", async () => {
  const navStyles = await readFile(new URL("src/styles/floating-layout.css", webRoot), "utf8");

  assert.match(navStyles, /--floating-nav-foreground:\s*rgba\(255,\s*255,\s*255,\s*\.62\)/);
  assert.match(navStyles, /--floating-nav-active-background:\s*#f2f3ef/);
  assert.match(navStyles, /border:\s*1px solid rgba\(255,\s*255,\s*255,\s*\.11\)/);
  assert.match(navStyles, /rgba\(34,\s*40,\s*31,\s*\.74\)/);
  assert.match(navStyles, /rgba\(10,\s*14,\s*8,\s*\.30\)/);
  assert.match(navStyles, /\.floating-nav-button:focus-visible/);
});
