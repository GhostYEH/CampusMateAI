import test from "node:test";
import assert from "node:assert/strict";

import { scenePayloadOf } from "../src/features/magicclass/useNativeClassmates.js";

test("同学上下文保留题干与选项，但不夹带答案、解析和提示", () => {
  const scene = {
    id: "quiz-1",
    stageId: "stage-1",
    type: "quiz",
    content: {
      type: "quiz",
      title: "极限测验",
      questions: [
        {
          id: "q1",
          question: "当 x 趋近于 0 时，下面哪个极限等于 1？",
          options: [
            { id: "a", text: "sin(x)/x" },
            { id: "b", text: "cos(x)/x" },
          ],
          answer: "SENTINEL_ANSWER",
          analysis: "SENTINEL_ANALYSIS",
          hints: ["SENTINEL_HINT"],
          commentPrompt: "SENTINEL_COMMENT",
        },
      ],
    },
  };

  const payload = scenePayloadOf(scene, { title: "极限测验", type: "quiz" }, "quiz-1");
  assert.equal(payload.id, "quiz-1");
  assert.equal(payload.content.type, "quiz");
  assert.match(payload.content.text, /哪个极限等于 1/);
  assert.match(payload.content.text, /sin\(x\)\/x/);
  for (const sentinel of ["SENTINEL_ANSWER", "SENTINEL_ANALYSIS", "SENTINEL_HINT", "SENTINEL_COMMENT"]) {
    assert.doesNotMatch(payload.content.text, new RegExp(sentinel), `答案字段 ${sentinel} 不得进入同学上下文`);
  }
});

test("非测验场景的普通正文不会被误删", () => {
  const scene = {
    id: "slide-1",
    content: { type: "slide", title: "函数极限", body: "先看左极限，再看右极限。" },
  };
  const payload = scenePayloadOf(scene, { title: "函数极限", type: "slide" }, "slide-1");
  assert.match(payload.content.text, /左极限/);
  assert.match(payload.content.text, /右极限/);
});
