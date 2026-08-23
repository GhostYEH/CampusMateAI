import assert from "node:assert/strict";
import test from "node:test";

import { createSpeechEndpoint, createUnitySpeechMessage, normalizeRuntimeConfig } from "../../../public/digital-human/mobileRuntime.js";

test("normalizes the injected API configuration without persisting provider secrets", () => {
  assert.deepEqual(
    normalizeRuntimeConfig({ apiBaseUrl: "http://127.0.0.1:8000/api/v1/", accessToken: " bearer-token " }),
    { apiBaseUrl: "http://127.0.0.1:8000/api/v1", accessToken: "bearer-token" },
  );
});
test("builds the authenticated TTS endpoint", () => {
  assert.equal(createSpeechEndpoint("https://campus.example/api/v1/"), "https://campus.example/api/v1/assistant/tts");
});

test("clamps live playback levels before forwarding them to Unity", () => {
  assert.deepEqual(createUnitySpeechMessage("speech-level", 2), {
    source: "campusmate",
    type: "speech-level",
    value: 1,
  });
  assert.deepEqual(createUnitySpeechMessage("speech-state", true), {
    source: "campusmate",
    type: "speech-state",
    value: true,
  });
});
