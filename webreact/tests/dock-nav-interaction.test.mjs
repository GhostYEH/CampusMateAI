import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(new URL("../src/components/FloatingNav/LiquidMetalNav.jsx", import.meta.url), "utf8");
const buttonStyles = fs.readFileSync(new URL("../src/styles/button-effects.css", import.meta.url), "utf8");
const layoutStyles = fs.readFileSync(new URL("../src/styles/floating-layout.css", import.meta.url), "utf8");

test("floating navigation applies spring proximity scaling to every dock item", () => {
  assert.match(source, /from "motion\/react"/);
  assert.match(source, /useMotionValue/);
  assert.match(source, /useSpring/);
  assert.match(source, /useTransform/);
  assert.match(source, /getDockScale/);
  assert.match(source, /onMouseMove/);
  assert.match(source, /style=\{\{ scale:/);
  assert.match(source, /dockMagnification = 60/);
  assert.match(source, /dockBaseItemSize = 44/);
});

test("floating navigation caches item geometry instead of reading layout during pointer scaling", () => {
  const dockItemSource = source.slice(source.indexOf("function DockItem"), source.indexOf("export default function LiquidMetalNav"));

  assert.match(source, /useLayoutEffect/);
  assert.match(source, /ResizeObserver/);
  assert.match(source, /Array\.from\(list\.children\)\.forEach/);
  assert.doesNotMatch(dockItemSource, /getBoundingClientRect/);
});

test("floating navigation coalesces pointer updates to one animation frame", () => {
  assert.match(source, /requestAnimationFrame/);
  assert.match(source, /cancelAnimationFrame/);
});

test("floating navigation mounts the liquid renderer for pointer and focus interaction", () => {
  assert.match(source, /LiquidMetalButton/);
  assert.match(source, /variant="nav"/);
  assert.match(source, /disableEffects=\{reduceMotion\}/);
  assert.doesNotMatch(source, /disableEffects=\{reduceMotion \|\| !active\}/);
  assert.match(source, /defer/);
  assert.match(source, /maxFps=\{20\}/);
  assert.match(source, /dprCap=\{1\}/);
});

test("floating navigation disables proximity scaling when reduced motion is enabled", () => {
  assert.match(source, /reduceMotion \? 1 : [a-zA-Z]+/);
  assert.match(source, /data-reduce-motion/);
});

test("floating navigation replaces the static hover highlight with liquid motion", () => {
  assert.match(buttonStyles, /\.sylva-liquid-stage--nav\[data-active="true"\] \.sylva-liquid-plate/);
  assert.doesNotMatch(buttonStyles, /\.sylva-liquid-stage--nav:hover \.sylva-liquid-plate/);
  assert.doesNotMatch(buttonStyles, /\.sylva-liquid-stage--nav\.hot \.sylva-liquid-plate/);
  assert.doesNotMatch(
    layoutStyles,
    /\.floating-nav-button:hover,\s*\.floating-nav-list > li\.active \.floating-nav-button/,
  );
  assert.match(layoutStyles, /\.floating-nav-list > li\.active \.floating-nav-button\s*\{/);
});
