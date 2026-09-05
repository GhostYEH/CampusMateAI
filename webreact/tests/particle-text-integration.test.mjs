import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const footer = await readFile(new URL("../src/components/HomeFooter.jsx", import.meta.url), "utf8");
const particleText = await readFile(new URL("../src/components/ParticleText.jsx", import.meta.url), "utf8");

test("homepage brand footer integrates the React Bits particle text contract", () => {
  assert.match(footer, /import ParticleText from ["']\.\/ParticleText\.jsx["']/);
  assert.match(footer, /<ParticleText[\s\S]*text="CAMPUSMATE"/);
  assert.match(footer, /trigger="hover"/);
  assert.match(footer, /animateOnMount=\{false\}/);
  assert.match(footer, /scatter=\{0\}/);
  assert.match(footer, /gatherDuration=\{1\}/);
  assert.match(footer, /stagger=\{0\}/);
  assert.match(footer, /color="#f8fcff"/);
  assert.match(footer, /highlightColor="#c8d8ff"/);
  assert.match(footer, /fontSize="clamp\(4\.5rem, 16vw, 11rem\)"/);
  assert.match(particleText, /const sampleText = async \(\) =>/);
  assert.match(particleText, /animateOnMount = true/);
  assert.match(particleText, /getImageData\(/);
  assert.match(particleText, /pointerRepel/);
  assert.match(particleText, /startGather\(true\)/);
});
