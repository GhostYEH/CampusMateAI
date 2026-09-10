import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const appShell = readFileSync(new URL("../src/components/AppShell.jsx", import.meta.url), "utf8");
const floatingNav = readFileSync(new URL("../src/components/FloatingNav/FloatingNav.jsx", import.meta.url), "utf8");
const preloadModule = new URL("../src/app/routePreload.js", import.meta.url);
const visualEffectBoundary = new URL("../src/components/VisualEffectBoundary.jsx", import.meta.url);

test("primary navigation preloads the target route on pointer or keyboard intent", () => {
  assert.doesNotThrow(() => readFileSync(preloadModule, "utf8"));
  assert.match(appShell, /preloadRoute/);
  assert.match(appShell, /<FloatingNav[\s\S]*onIntent=\{preloadRoute\}/);
  assert.match(floatingNav, /onPointerOver/);
  assert.match(floatingNav, /onFocusCapture/);
  assert.match(floatingNav, /onIntent\?\.\(`\/\$\{item\.key\}`\)/);
});

test("adaptive nav contrast does not poll WebGL pixels continuously", () => {
  assert.doesNotMatch(floatingNav, /setInterval/);
  assert.doesNotMatch(floatingNav, /readPixels/);
  assert.match(floatingNav, /setAttribute\("data-contrast", "dark"\)/);
});

test("route-specific shader backgrounds load only when their route renders", () => {
  assert.doesNotMatch(appShell, /import Iridescence/);
  assert.doesNotMatch(appShell, /import Prism/);
  assert.match(appShell, /lazy\(\(\) => import\("\.\/Iridescence\.jsx"\)\)/);
  assert.match(appShell, /lazy\(\(\) => import\("\.\/Prism\.jsx"\)\)/);
});

test("a failed decorative shader chunk degrades without replacing route content", () => {
  const boundarySource = readFileSync(visualEffectBoundary, "utf8");
  assert.match(appShell, /import VisualEffectBoundary from ["']\.\/VisualEffectBoundary\.jsx["']/);
  assert.match(appShell, /<VisualEffectBoundary>[\s\S]*<Suspense fallback=\{null\}>/);
  assert.match(boundarySource, /getDerivedStateFromError/);
  assert.match(boundarySource, /return null/);
});
