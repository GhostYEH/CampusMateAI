import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import { STUDY_SCENE_ASSETS, STUDY_SCENES, readStudyScene, saveStudyScene } from "../src/features/study/scenes.js";

const roomSource = await readFile(new URL("../src/components/study/SummerFocusRoom.jsx", import.meta.url), "utf8");
const studyStyles = await readFile(new URL("../src/styles/study-summer.css", import.meta.url), "utf8");

test("study scene metadata keeps the original three scenes and adds two natural backgrounds", () => {
  assert.deepEqual(STUDY_SCENES.map((scene) => scene.key), ["rain", "snow", "cloud", "bamboo", "coast"]);
  assert.equal(STUDY_SCENE_ASSETS.bamboo, "/assets/study/study-bamboo-mist.png");
  assert.equal(STUDY_SCENE_ASSETS.coast, "/assets/study/study-coastal-dusk.png");
  assert.equal(STUDY_SCENES.length, 5);
});

test("study scene persistence accepts both generated scenes", () => {
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key) || null,
    setItem: (key, value) => values.set(key, value),
  };

  assert.equal(saveStudyScene("bamboo", storage), "bamboo");
  assert.equal(readStudyScene(storage), "bamboo");
  assert.equal(saveStudyScene("coast", storage), "coast");
  assert.equal(readStudyScene(storage), "coast");
});

test("focus room uses the supplied AccordionGallery as its scene switcher", () => {
  assert.match(roomSource, /import AccordionGallery from ["']\.\/AccordionGallery\.jsx["']/);
  assert.match(roomSource, /<AccordionGallery/);
  assert.match(roomSource, /onChange=\{onSelectScene\}/);
  assert.match(roomSource, /trigger=["']click["']/);
});

test("all five study scenes are available to full-page and immersive backgrounds", () => {
  assert.match(studyStyles, /study-bamboo-mist\.png/);
  assert.match(studyStyles, /study-coastal-dusk\.png/);
  assert.match(studyStyles, /data-study-scene=["']bamboo["']/);
  assert.match(studyStyles, /data-study-scene=["']coast["']/);
  assert.match(studyStyles, /data-immersive-scene=["']bamboo["']/);
  assert.match(studyStyles, /data-immersive-scene=["']coast["']/);
});
