import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const homeFooter = await readFile(new URL("../src/components/HomeFooter.jsx", import.meta.url), "utf8");
const particleText = await readFile(new URL("../src/components/ParticleText.jsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");

test("homepage brand footer keeps its particle field and animated backdrop", () => {
  assert.match(homeFooter, /<ParticleText[\s\S]*highlightColor="#c8d8ff"/);
  assert.match(particleText, /const targets = \[\];/);
  assert.match(particleText, /getImageData\(/);
  assert.match(particleText, /particles\.forEach\(/);
  assert.match(particleText, /requestAnimationFrame\(render\)/);
  assert.match(styles, /\.home-footer-brand::before[\s\S]*radial-gradient/);
  assert.match(styles, /\.home-footer-brand::after[\s\S]*box-shadow/);
});
