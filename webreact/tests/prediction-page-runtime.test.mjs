import { readFileSync } from "node:fs";
import { test } from "node:test";
import assert from "node:assert/strict";

const page = readFileSync(new URL("../src/pages/PredictionPage.jsx", import.meta.url), "utf8");
const nav = readFileSync(new URL("../src/components/FloatingNav/navItems.js", import.meta.url), "utf8");
const floatingNav = readFileSync(new URL("../src/components/FloatingNav/FloatingNav.jsx", import.meta.url), "utf8");

test("prediction page starts data loading from effects rather than inert refs", () => {
  assert.match(page, /useEffect\(\(\) => \{\s*mounted\.current = true;/);
  assert.match(page, /useEffect\(\(\) => \{\s*let cancelled = false;/);
  assert.doesNotMatch(page, /useRef\(\(\) => \{/);
});

test("world model has a discoverable navigation entry covering prediction", () => {
  assert.match(nav, /key:\s*["']learning-state["']/);
  assert.match(nav, /label:\s*["']学习模型["']/);
  assert.match(floatingNav, /WORLD_MODEL_ROUTE_PREFIXES/);
  assert.match(floatingNav, /["']prediction["']/);
});
