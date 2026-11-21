import test from "node:test";
import assert from "node:assert/strict";

import {
  CAMPUS_INK,
  CAMPUS_PAPER,
  campusBackground,
  campusElements,
  campusTheme,
} from "../src/features/magicclass/slideTheme.js";

test("missing or pure-white slide backgrounds become campus paper", () => {
  assert.deepEqual(campusBackground(undefined), { type: "solid", color: CAMPUS_PAPER });
  assert.equal(campusBackground({ type: "solid", color: "#fff" }).color, CAMPUS_PAPER);
  assert.equal(campusBackground({ type: "solid", color: "#FFFFFF" }).color, CAMPUS_PAPER);
  // 旧导入链路用 `type: "color"`；渲染器不认这个类型，必须先归一成 solid，
  // 否则课堂会退回默认白底。
  const legacy = campusBackground({ type: "color", color: "#fff" });
  assert.equal(legacy.type, "solid");
  assert.equal(legacy.color, CAMPUS_PAPER);
  const legacyBrand = campusBackground({ type: "color", color: "#153B34" });
  assert.equal(legacyBrand.type, "solid");
  assert.equal(legacyBrand.color, "#153B34");
});

test("image and gradient backgrounds are not rewritten", () => {
  const image = { type: "image", image: { src: "cover.png", size: "cover" } };
  const gradient = { type: "gradient", gradient: { colors: [] } };
  assert.deepEqual(campusBackground(image), image);
  assert.deepEqual(campusBackground(gradient), gradient);
});

test("default dark text becomes campus ink, explicit colors stay", () => {
  assert.equal(campusTheme(undefined, { type: "solid", color: CAMPUS_PAPER }).fontColor, CAMPUS_INK);
  assert.equal(campusTheme({ fontColor: "#333333" }, { type: "solid", color: CAMPUS_PAPER }).fontColor, CAMPUS_INK);
  assert.equal(campusTheme({ fontColor: "#DAB27A" }, { type: "solid", color: CAMPUS_PAPER }).fontColor, "#DAB27A");
});

test("dark slide backgrounds switch default text to paper", () => {
  const theme = campusTheme({ fontColor: "#000000" }, { type: "solid", color: "#153B34" });
  assert.equal(theme.fontColor, CAMPUS_PAPER);
  assert.equal(theme.fontName, "Microsoft YaHei");
});

test("theme keeps an explicit font family", () => {
  assert.equal(campusTheme({ fontName: "Noto Sans SC" }, undefined).fontName, "Noto Sans SC");
});

test("legacy dark text elements become campus ink, shapes and explicit colors stay", () => {
  const elements = [
    { id: "title", type: "text", defaultColor: "#333333" },
    { id: "plain", type: "text" },
    { id: "amber", type: "text", defaultColor: "#DAB27A" },
    { id: "card", type: "shape", fill: "#ffffff" },
  ];
  const themed = campusElements(elements, CAMPUS_INK);
  assert.equal(themed[0].defaultColor, CAMPUS_INK);
  assert.equal(themed[1].defaultColor, CAMPUS_INK);
  assert.equal(themed[2].defaultColor, "#DAB27A");
  assert.deepEqual(themed[3], elements[3]);
});
