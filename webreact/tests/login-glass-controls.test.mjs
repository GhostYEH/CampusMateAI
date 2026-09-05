import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const loginPage = await readFile(new URL("../src/pages/LoginPage.jsx", import.meta.url), "utf8");
const glassSource = await readFile(new URL("../src/components/GlassSurface.jsx", import.meta.url), "utf8").catch(() => "");
const glassStyles = await readFile(new URL("../src/components/GlassSurface.css", import.meta.url), "utf8").catch(() => "");
const pageStyles = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");

test("login controls use GlassSurface without covering the whole liquid background", () => {
  assert.match(loginPage, /import GlassSurface from ["']\.\.\/components\/GlassSurface\.jsx["']/);
  assert.match(loginPage, /className=["']login-mode-glass["']/);
  assert.match(loginPage, /className=["']login-input-glass["']/);
  assert.match(loginPage, /className=["']login-button-glass["']/);
  assert.match(loginPage, /<LiquidChrome[\s\S]*className=["']login-panel-liquid["']/);
});

test("GlassSurface provides the requested glass filter and fallback", () => {
  assert.match(glassSource, /useId/);
  assert.match(glassSource, /feDisplacementMap/);
  assert.match(glassSource, /ResizeObserver/);
  assert.match(glassStyles, /\.glass-surface--svg/);
  assert.match(glassStyles, /\.glass-surface--fallback/);
  assert.match(glassStyles, /backdrop-filter/);
});

test("login controls keep high-contrast white and blue surfaces", () => {
  assert.match(pageStyles, /\.login-input-glass[\s\S]*background:\s*rgba\(255,255,255,\.86\)/);
  assert.match(pageStyles, /\.login-button-glass[\s\S]*background:\s*rgba\(50,103,214,\.88\)/);
  assert.match(pageStyles, /\.login-panel-head h2[\s\S]*color:\s*#fff/);
  assert.match(pageStyles, /\.login-form > label[\s\S]*color:\s*#fff/);
});
