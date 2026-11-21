import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const screenCanvasSource = readFileSync(
  new URL("../src/magicclass/slide/Editor/ScreenCanvas.jsx", import.meta.url),
  "utf8",
);

test("playback canvas subscribes to and renders timeline spotlight state", () => {
  assert.match(screenCanvasSource, /useCanvasStore\.use\.spotlightElementId\(\)/);
  assert.match(screenCanvasSource, /useCanvasStore\.use\.spotlightOptions\(\)/);
  assert.match(
    screenCanvasSource,
    /<SpotlightOverlay[\s\S]*?options=\{\{[\s\S]*?elementId:\s*effectsEnabled \? spotlightElementId : ''[\s\S]*?\.\.\.spotlightOptions[\s\S]*?\}\}/,
  );
  assert.match(screenCanvasSource, /elementIdPrefix=\{elementIdPrefix\}/);
  assert.match(screenCanvasSource, /elementIdPrefix = SCREEN_ELEMENT_ID_PREFIX/);
  const classroomSource = readFileSync(
    new URL("../src/components/magicclass/magicclassClassroomStage.jsx", import.meta.url),
    "utf8",
  );
  assert.match(classroomSource, /<MagicClassSlideSurface[\s\S]*?canvas=\{canvas\}[\s\S]*?elementIdPrefix=\{`thumb-\$\{sceneId/);
});

test("canvasless generated slides use the campus paper template, not a plain white box", () => {
  const source = readFileSync(
    new URL("../src/magicclass/scene/scene-renderer.jsx", import.meta.url),
    "utf8",
  );
  assert.match(source, /#F2F1E8/);
  assert.match(source, /#153B34/);
  assert.match(source, /CampusMate · 课堂讲义/);
  assert.match(source, /overflow-y-auto/);
  assert.match(source, /\.cm-slide-prose \.prose \{ max-width: none; font-size: inherit;/);
});

test("empty action plans still focus a title element instead of doing nothing", () => {
  const classroom = readFileSync(
    new URL("../src/components/magicclass/magicclassClassroomStage.jsx", import.meta.url),
    "utf8",
  );
  assert.match(classroom, /keyTextElementId\(scene\)/);
  assert.match(classroom, /setSpotlight\(keyId, \{ dimness: 0\.55 \}\)/);
  assert.match(classroom, /已聚焦标题 2\.4 秒/);
});

test("canvasless title gets a visible focus pulse when playback has no actions", () => {
  const renderer = readFileSync(
    new URL("../src/magicclass/scene/scene-renderer.jsx", import.meta.url),
    "utf8",
  );
  const classroom = readFileSync(
    new URL("../src/components/magicclass/magicclassClassroomStage.jsx", import.meta.url),
    "utf8",
  );
  assert.match(renderer, /id="campus-fallback-title"/);
  assert.match(renderer, /cm-slide-focus/);
  assert.match(classroom, /getElementById\("campus-fallback-title"\)/);
  assert.match(classroom, /已强调标题 2\.4 秒/);
});
