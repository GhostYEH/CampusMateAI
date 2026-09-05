import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(new URL("../src/components/FloatingNav/GooeyNav.jsx", import.meta.url), "utf8");

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

test("floating navigation disables proximity scaling when reduced motion is enabled", () => {
  assert.match(source, /reduceMotion \? 1 : [a-zA-Z]+/);
  assert.match(source, /data-reduce-motion/);
});
