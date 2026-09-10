import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const footer = await readFile(new URL("../src/components/HomeFooter.jsx", import.meta.url), "utf8");
const particleText = await readFile(new URL("../src/components/ParticleText.jsx", import.meta.url), "utf8");

test("homepage brand footer integrates the React Bits particle text contract", () => {
  assert.match(footer, /import ParticleText from ["']\.\/ParticleText\.jsx["']/);
  assert.match(footer, /<ParticleText[\s\S]*text="Campus Mate"/);
  assert.match(footer, /trigger="none"/);
  assert.match(footer, /particleSize=\{2\.3\}/);
  assert.match(footer, /density=\{6\}/);
  assert.match(footer, /scatter=\{180\}/);
  assert.match(footer, /gatherDuration=\{1600\}/);
  assert.match(footer, /stagger=\{780\}/);
  assert.match(footer, /pointerRepel=\{52\}/);
  assert.match(footer, /repelRadius=\{110\}/);
  assert.match(footer, /idleDrift=\{0\.7\}/);
  assert.match(footer, /color="#ffffff"/);
  assert.match(footer, /highlightColor="#9a7ae4"/);
  assert.match(footer, /fontSize="clamp\(3rem, 12vw, 8rem\)"/);
  assert.match(footer, /fontWeight=\{900\}/);
  assert.match(footer, /animateOnMount=\{false\}/);
  assert.match(particleText, /const sampleText = async \(\) =>/);
  assert.match(particleText, /animateOnMount = true/);
  assert.match(particleText, /getImageData\(/);
  assert.match(particleText, /pointerRepel/);
  assert.match(particleText, /startGather\(true\)/);
});
