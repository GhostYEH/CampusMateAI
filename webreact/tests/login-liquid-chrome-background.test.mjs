import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const packageJson = JSON.parse(await readFile(new URL("../package.json", import.meta.url), "utf8"));
const loginPage = await readFile(new URL("../src/pages/LoginPage.jsx", import.meta.url), "utf8");
const liquidSource = await readFile(new URL("../src/components/LiquidChrome.jsx", import.meta.url), "utf8").catch(() => "");
const liquidStyles = await readFile(new URL("../src/components/LiquidChrome.css", import.meta.url), "utf8").catch(() => "");
const pageStyles = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");

test("login panel uses LiquidChrome and removes the old Dither background", () => {
  assert.match(loginPage, /import LiquidChrome from ["']\.\.\/components\/LiquidChrome\.jsx["']/);
  assert.match(loginPage, /<LiquidChrome[\s\S]*className=["']login-panel-liquid["']/);
  assert.match(loginPage, /baseColor=\{\[0\.1, 0\.1, 0\.1\]\}/);
  assert.match(loginPage, /speed=\{1\}/);
  assert.match(loginPage, /amplitude=\{0\.6\}/);
  assert.match(loginPage, /interactive=\{true\}/);
  assert.doesNotMatch(loginPage, /Dither|dither/);
});

test("LiquidChrome keeps the requested animated interactive canvas behavior", () => {
  assert.match(liquidSource, /from ["']ogl["']/);
  assert.match(liquidSource, /Renderer/);
  assert.match(liquidSource, /Program/);
  assert.match(liquidSource, /Mesh/);
  assert.match(liquidSource, /Triangle/);
  assert.match(liquidSource, /requestAnimationFrame/);
  assert.match(liquidSource, /mousemove/);
  assert.match(liquidSource, /touchmove/);
  assert.match(liquidStyles, /\.liquidChrome-container[\s\S]*width:\s*100%/);
  assert.match(liquidStyles, /\.liquidChrome-container[\s\S]*height:\s*100%/);
});

test("login panel avoids an inner scrollbar and prevents chrome highlights from clipping to white", () => {
  assert.match(pageStyles, /\.login-panel\s*\{\s*max-height:\s*none;\s*overflow:\s*hidden;/);
  assert.match(pageStyles, /\.login-panel\s*\{\s*max-height:\s*none;\s*overflow:\s*hidden;\s*background:\s*transparent;/);
  assert.match(pageStyles, /\.login-panel-liquid\s*\{\s*opacity:\s*1;/);
  assert.match(liquidSource, /uBaseColor \/ abs\(sin\(uTime - uv\.y - uv\.x\)\)/);
});

test("LiquidChrome uses the existing OGL dependency", () => {
  assert.ok(packageJson.dependencies.ogl);
});
