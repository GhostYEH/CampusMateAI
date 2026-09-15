import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const packageJson = JSON.parse(await readFile(new URL("../package.json", import.meta.url), "utf8"));
const appSource = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
const shellSource = await readFile(new URL("../src/components/AppShell.jsx", import.meta.url), "utf8");
const navSource = await readFile(new URL("../src/components/FloatingNav/FloatingNav.jsx", import.meta.url), "utf8");

test("shell keeps OpenGlass side controls while navigation uses the homepage liquid-metal treatment", () => {
  assert.equal(packageJson.dependencies["open-glass-ui"], "^0.3.0");
  assert.match(appSource, /GlassSystemProvider/);
  assert.match(shellSource, /SearchField/);
  assert.match(shellSource, /Avatar/);
  assert.match(shellSource, /IconButton/);
  assert.doesNotMatch(navSource, /import \{ Glass \} from "open-glass-ui"/);
  assert.match(navSource, /className="floating-nav floating-nav--primary"/);
});

test("side-control material follows its scene without branching the global navigation", () => {
  assert.match(appSource, /theme=\{\{ appearance: "light"/);
  assert.match(shellSource, /const topbarGlassTone = isHome \|\| isStudy \? "dark" : "light";/);
  assert.match(shellSource, /className="topbar-search-surface"[\s\S]*data-tone=\{tone\}/);
  assert.match(shellSource, /className="topbar-info-surface"[\s\S]*data-tone=\{topbarGlassTone\}/);
  assert.doesNotMatch(shellSource, /<FloatingNav tone=/);
});

test("navigation no longer depends on the local glass surface", () => {
  assert.doesNotMatch(navSource, /LiquidGlassSurface/);
  assert.doesNotMatch(shellSource, /LiquidGlassSurface/);
});
