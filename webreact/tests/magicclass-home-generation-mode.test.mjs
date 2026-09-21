import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

const model = await import(new URL("../src/features/magicclass/homeGenerationModel.js", import.meta.url));
const homeSource = fs.readFileSync(new URL("../src/components/magicclass/magicclassHome.jsx", import.meta.url), "utf8");

test("routes experiment requests to the interactive simulation runtime", () => {
  assert.equal(model.inferHomeGenerationMode("设计验证牛顿第二定律的实验，说明变量和误差分析"), "simulation");
});

test("routes team research and presentation requests to PBL", () => {
  assert.equal(model.inferHomeGenerationMode("围绕校园节能方案设计一个小组调研和成果展示任务"), "pbl");
});

test("keeps explanatory practice requests as slides so the quiz scene is retained", () => {
  assert.equal(model.inferHomeGenerationMode("用三页讲解牛顿第二定律并加入一道选择题"), "slide");
});

test("homepage submits the inferred mode through the real generation API", () => {
  assert.match(homeSource, /inferHomeGenerationMode\(topic\)/);
  assert.match(homeSource, /api\.generateMagicClassHome/);
});
