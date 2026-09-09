import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const viteConfig = readFileSync(new URL("../vite.config.mjs", import.meta.url), "utf8");
const mainSource = readFileSync(new URL("../src/main.jsx", import.meta.url), "utf8");
const homeSceneSource = readFileSync(new URL("../src/components/SylvaHomeHero.jsx", import.meta.url), "utf8");

test("route-only 3D libraries stay out of the shared startup vendor chunk", () => {
  assert.match(viteConfig, /onlyExplicitManualChunks:\s*true/);
  assert.match(viteConfig, /moduleId\.endsWith\("\.css"\)\) return undefined/);
  assert.match(viteConfig, /@designcodeio\/threeui[\s\S]*return "route-3d-vendor"/);
  assert.match(viteConfig, /@react-three[\s\S]*return "route-3d-vendor"/);
  assert.match(viteConfig, /node_modules\/three\/[\s\S]*return "route-3d-vendor"/);
  assert.match(viteConfig, /node_modules\/three-stdlib\//);
});

test("ThreeUI styles load with their lazy scene instead of every initial route", () => {
  assert.doesNotMatch(mainSource, /@designcodeio\/threeui\/style\.css/);
  assert.match(homeSceneSource, /@designcodeio\/threeui\/style\.css/);
});

test("shared dependencies use automatic chunking instead of a circular catch-all vendor chunk", () => {
  assert.match(viteConfig, /return undefined/);
  assert.doesNotMatch(viteConfig, /return "vendor"/);
  assert.doesNotMatch(viteConfig, /return "react-vendor"/);
});
