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
  assert.match(heroSource, /data-campusmate-nav/);
  assert.match(heroSource, /\.dock-wrap\{display:none!important\}/);
  assert.match(homeSource, /<SylvaHomeHero/);
  assert.match(homeSource, /id=["']campus-dashboard["']/);
  assert.match(homeSource, /<ClassicHome|<GamifiedHome/);
});

test("global navigation preserves the project's original blue liquid-glass states", async () => {
  const navStyles = await readFile(new URL("src/styles/floating-layout.css", webRoot), "utf8");

  assert.match(navStyles, /--floating-nav-foreground:\s*#53627b/);
  assert.match(navStyles, /--floating-nav-active-background:\s*rgb\(231\s+239\s+255\s*\/\s*92%\)/);
  assert.match(navStyles, /--floating-nav-active-background:\s*rgb\(72\s+108\s+211\s*\/\s*72%\)/);
  assert.match(navStyles, /--floating-nav-active-background:\s*rgb\(89\s+133\s+224\s*\/\s*30%\)/);
  assert.doesNotMatch(navStyles, /rgba\(34,\s*40,\s*31,\s*\.74\)/);
});
