import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { getTypingDelay, getTypingFrame } from "../src/components/typingPlaceholder.js";

const appSource = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
const layerSource = await readFile(new URL("../src/components/TypingPlaceholderLayer.jsx", import.meta.url), "utf8").catch(() => "");
const stylesSource = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");

test("typing frames reveal characters and keep a trailing cursor while in progress", () => {
  assert.equal(getTypingFrame("搜索课程", 0, true), "▏");
  assert.equal(getTypingFrame("搜索课程", 2, true), "搜索▏");
  assert.equal(getTypingFrame("搜索课程", 4, false), "搜索课程");
});

test("typing delay stays positive and uses the configured mean when variance is zero", () => {
  assert.equal(getTypingDelay(70, 0, () => 0.5), 70);
  assert.ok(getTypingDelay(70, 25, () => 0.99) > 0);
});

test("global placeholder layer is mounted once for login and lazy routes", () => {
  assert.match(appSource, /import TypingPlaceholderLayer from ["']\.\/components\/TypingPlaceholderLayer\.jsx["']/);
  assert.match(appSource, /<AppProvider>\s*<TypingPlaceholderLayer \/>\s*<Routes>/);
  assert.match(layerSource, /input:not\(\[type=["']hidden["']\]\)/);
  assert.match(layerSource, /textarea/);
  assert.match(layerSource, /MutationObserver/);
  assert.match(layerSource, /addEventListener\(["']input["']/);
  assert.match(layerSource, /data-typing-placeholder-source/);
  assert.match(layerSource, /prefers-reduced-motion/);
});

test("typing placeholder styles honor reduced motion", () => {
  assert.match(stylesSource, /\.is-typing-placeholder/);
  assert.match(stylesSource, /prefers-reduced-motion:\s*reduce[\s\S]*\.is-typing-placeholder/);
});
