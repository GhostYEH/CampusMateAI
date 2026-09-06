import test from "node:test";
import assert from "node:assert/strict";

import { STUDY_BACKGROUNDS, pickStudyBackground } from "../src/features/study/backgrounds.js";

test("study companion exposes the five supplied backgrounds", () => {
  assert.deepEqual(STUDY_BACKGROUNDS, [
    "/assets/study/study-lake-sunrise.png",
    "/assets/study/study-forest-stream.png",
    "/assets/study/study-sea-sunset.png",
    "/assets/study/study-rain-window.png",
    "/assets/study/study-autumn-campus.png",
  ]);
});

test("study companion maps a page-entry random value to one background", () => {
  assert.equal(pickStudyBackground(() => 0), STUDY_BACKGROUNDS[0]);
  assert.equal(pickStudyBackground(() => 0.4), STUDY_BACKGROUNDS[2]);
  assert.equal(pickStudyBackground(() => 0.999999), STUDY_BACKGROUNDS[4]);
});
