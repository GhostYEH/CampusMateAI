import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const packageJson = JSON.parse(await readFile(new URL("../package.json", import.meta.url), "utf8"));
const loginPage = await readFile(new URL("../src/pages/LoginPage.jsx", import.meta.url), "utf8");
const tiltedSource = await readFile(new URL("../src/components/TiltedCard.jsx", import.meta.url), "utf8").catch(() => "");
const tiltedStyles = await readFile(new URL("../src/components/TiltedCard.css", import.meta.url), "utf8").catch(() => "");

test("login panel is wrapped by the tilted card interaction", () => {
  assert.match(loginPage, /import TiltedCard from ["']\.\.\/components\/TiltedCard\.jsx["']/);
  assert.match(loginPage, /<TiltedCard[\s\S]*className=["']login-panel-tilted["']/);
  assert.match(loginPage, /<TiltedCard[\s\S]*<section className=["']login-panel["']/);
});

test("login panel uses the requested TiltedCard intensity", () => {
  assert.match(loginPage, /rotateAmplitude=\{20\}/);
  assert.match(loginPage, /scaleOnHover=\{1\.2\}/);
});

test("tilted card supports form children and cursor-driven transforms", () => {
  assert.match(tiltedSource, /from ["']motion\/react["']/);
  assert.match(tiltedSource, /children/);
  assert.match(tiltedSource, /rotateX/);
  assert.match(tiltedSource, /rotateY/);
  assert.match(tiltedSource, /onMouseMove/);
  assert.match(tiltedSource, /onMouseLeave/);
  assert.match(tiltedStyles, /perspective:\s*800px/);
  assert.match(tiltedStyles, /transform-style:\s*preserve-3d/);
});

test("motion is declared for the React client", () => {
  assert.ok(packageJson.dependencies.motion);
});
