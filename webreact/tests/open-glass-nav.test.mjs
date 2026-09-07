import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const packageJson = JSON.parse(await readFile(new URL("../package.json", import.meta.url), "utf8"));
const appSource = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
const shellSource = await readFile(new URL("../src/components/AppShell.jsx", import.meta.url), "utf8");
const navSource = await readFile(new URL("../src/components/FloatingNav/FloatingNav.jsx", import.meta.url), "utf8");

test("navigation uses the OpenGlass provider and official components", () => {
  assert.equal(packageJson.dependencies["open-glass-ui"], "^0.3.0");
  assert.match(appSource, /GlassSystemProvider/);
  assert.match(shellSource, /SearchField/);
  assert.match(shellSource, /Avatar/);
  assert.match(shellSource, /IconButton/);
  assert.match(navSource, /import \{ Glass \} from "open-glass-ui"/);
  assert.match(navSource, /<Glass[\s\S]*material="regular"[\s\S]*interactive/);
});

test("navigation no longer depends on the local glass surface", () => {
  assert.doesNotMatch(navSource, /LiquidGlassSurface/);
  assert.doesNotMatch(shellSource, /LiquidGlassSurface/);
});
