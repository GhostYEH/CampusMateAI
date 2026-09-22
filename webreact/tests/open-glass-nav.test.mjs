import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const packageJson = JSON.parse(await readFile(new URL("../package.json", import.meta.url), "utf8"));
const appSource = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
const shellSource = await readFile(new URL("../src/components/AppShell.jsx", import.meta.url), "utf8");
const navSource = await readFile(new URL("../src/components/FloatingNav/FloatingNav.jsx", import.meta.url), "utf8");

test("shell keeps OpenGlass content controls inside React Bits liquid glass", () => {
  assert.equal(packageJson.dependencies["open-glass-ui"], "^0.3.0");
  assert.match(appSource, /GlassSystemProvider/);
  assert.match(shellSource, /SearchField/);
  assert.match(shellSource, /Avatar/);
  assert.match(shellSource, /IconButton/);
  assert.match(shellSource, /import GlassSurface from "\.\/GlassSurface\.jsx"/);
  assert.doesNotMatch(shellSource, /LiquidMetalSurface/);
  assert.doesNotMatch(navSource, /import \{ Glass \} from "open-glass-ui"/);
  assert.match(navSource, /import GlassSurface from "\.\.\/GlassSurface\.jsx"/);
  assert.match(navSource, /className="floating-nav floating-nav--primary"/);
});

test("side controls share one scene-independent glass material with navigation", () => {
  assert.match(appSource, /theme=\{\{ appearance: "light"/);
  assert.match(shellSource, /function TopbarGlass\([\s\S]*<GlassSurface/);
  assert.match(shellSource, /className="topbar-search-surface"/);
  assert.match(shellSource, /className="topbar-info-surface"/);
  assert.doesNotMatch(shellSource, /topbarGlassTone|data-tone/);
  assert.doesNotMatch(shellSource, /<FloatingNav tone=/);
});

test("navigation depends on the shared React Bits glass surface, not the legacy wrapper", () => {
  assert.doesNotMatch(navSource, /LiquidGlassSurface/);
  assert.match(navSource, /GlassSurface/);
  assert.doesNotMatch(shellSource, /LiquidGlassSurface/);
});
