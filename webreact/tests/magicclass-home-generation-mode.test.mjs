import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

import { TOPIC_GENERATION_MODE } from "../src/features/magicclass/homeGenerationModel.js";

const generationSource = fs.readFileSync(new URL("../src/features/magicclass/useTopicClassroomGeneration.js", import.meta.url), "utf8");
const learningSpaceSource = fs.readFileSync(new URL("../src/pages/LearningSpaceHomePage.jsx", import.meta.url), "utf8");

test("the topic form requests a mixed lesson without requiring trigger words", () => {
  assert.equal(TOPIC_GENERATION_MODE, "adaptive");
  assert.match(generationSource, /api\.generateMagicClassHome\(courseId, \{\s+mode: TOPIC_GENERATION_MODE, prompt: topic/);
  assert.match(learningSpaceSource, /generation\.generate\(topic\)/);
});
