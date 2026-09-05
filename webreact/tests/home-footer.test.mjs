import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const reactRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("React home mounts the service and brand footer", async () => {
  const [classicHome, gamifiedHome, footer] = await Promise.all([
    readFile(path.join(reactRoot, "src/pages/home/ClassicHome.jsx"), "utf8"),
    readFile(path.join(reactRoot, "src/pages/home/GamifiedHome.jsx"), "utf8"),
    readFile(path.join(reactRoot, "src/components/HomeFooter.jsx"), "utf8"),
  ]);

  assert.match(`${classicHome}\n${gamifiedHome}`, /<HomeFooter>/);
  assert.match(`${classicHome}\n${gamifiedHome}`, /<\/HomeFooter>/);
  assert.match(`${classicHome}\n${gamifiedHome}\n${footer}`, /需要时再打开/);
  assert.match(footer, /我的课程/);
  assert.match(footer, /校园社区/);
  assert.match(footer, /关注微信公众号/);
  assert.match(footer, /下载移动端 App/);
  assert.match(footer, /y3288365856@gmail\.com/);
  assert.match(footer, /navigator\.clipboard/);
  assert.match(footer, /scrollTo\(/);
});

test("React footer keeps its visual system responsive", async () => {
  const css = await readFile(path.join(reactRoot, "src/styles.css"), "utf8");

  assert.match(css, /\.home-footer-info/);
  assert.match(css, /\.home-footer-main/);
  assert.match(css, /\.home-footer-brand \{[^}]*height: clamp\(/);
  assert.match(css, /\.home-footer-brand \{[^}]*background: linear-gradient\(/);
  assert.match(css, /\.home-footer-brand > \.particle-text \{[^}]*position: absolute/);
  assert.match(css, /\.home-footer-brand-caption \{/);
  assert.match(css, /\.home-foreground \{/);
  assert.match(css, /@media \(max-width: 760px\)/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
});
