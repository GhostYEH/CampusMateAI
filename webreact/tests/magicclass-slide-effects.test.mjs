import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const screenCanvasSource = readFileSync(
  new URL("../src/maic/slide/Editor/ScreenCanvas.jsx", import.meta.url),
  "utf8",
);

test("playback canvas subscribes to and renders timeline spotlight state", () => {
  assert.match(screenCanvasSource, /useCanvasStore\.use\.spotlightElementId\(\)/);
  assert.match(screenCanvasSource, /useCanvasStore\.use\.spotlightOptions\(\)/);
  assert.match(
    screenCanvasSource,
    /<SpotlightOverlay[\s\S]*?options=\{\{[\s\S]*?elementId:\s*effectsEnabled \? spotlightElementId : ''[\s\S]*?\.\.\.spotlightOptions[\s\S]*?\}\}/,
  );
  assert.match(screenCanvasSource, /elementIdPrefix="screen-element-"/);
  const classroomSource = readFileSync(
    new URL("../src/components/magicclass/magicclassClassroomStage.jsx", import.meta.url),
    "utf8",
  );
  assert.match(classroomSource, /<MaicSlideSurface canvas=\{canvas\} effectsEnabled=\{false\} \/>/);
});
