import { readFile } from "node:fs/promises";
import test from "node:test";
import assert from "node:assert/strict";

const pageSource = await readFile(new URL("../src/pages/NoticeCenterPage.jsx", import.meta.url), "utf8");
const styleSource = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");

test("notice page keeps the reference composition in the React tree", () => {
  assert.match(pageSource, /className="notifications-page"/);
  assert.match(pageSource, /className="notice-hero"/);
  assert.match(pageSource, /className="notice-layout"/);
  assert.match(pageSource, /className="notice-list-column"/);

  const heroIndex = pageSource.indexOf('className="notice-hero"');
  const layoutIndex = pageSource.indexOf('className="notice-layout"');
  const extractIndex = pageSource.indexOf('className="notice-extract-panel"');
  assert.ok(heroIndex >= 0 && heroIndex < layoutIndex);
  assert.ok(layoutIndex >= 0 && layoutIndex < extractIndex);
  assert.doesNotMatch(pageSource, /<Button variant="secondary" icon="PhSparkle">AI 整理<\/Button>/);
  assert.match(pageSource, /className="notice-hero-sparkle"/);
});

test("notice page has an intentional desktop split and mobile collapse", () => {
  assert.match(styleSource, /\.notifications-page\s*\{[\s\S]*?\}/);
  assert.match(styleSource, /\.notifications-page \.notice-layout\s*\{[\s\S]*?grid-template-columns:\s*minmax\(300px,\s*360px\)\s+minmax\(0,\s*1fr\)/);
  assert.match(styleSource, /@media \(max-width:\s*900px\)[\s\S]*?\.notifications-page \.notice-layout[\s\S]*?grid-template-columns:\s*1fr/);
});
