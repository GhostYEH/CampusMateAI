import assert from "node:assert/strict";
import test from "node:test";

import {
  createSpeechEndpoint,
  createUnitySpeechMessage,
  normalizeRuntimeConfig,
  PcmStreamPlayer,
  resolveDigitalHumanMode,
  resolveMobileLayout,
} from "../../../public/digital-human/mobileRuntime.js";

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

test("enables the compact host only for the Harmony layout query", () => {
  assert.equal(resolveMobileLayout("?layout=harmony"), "harmony");
  assert.equal(resolveMobileLayout("?layout=android"), "default");
  assert.equal(resolveMobileLayout(""), "default");
});

test("compatibility mode skips the Unity renderer while preserving the audio host", () => {
  assert.equal(resolveDigitalHumanMode("?embed=1&fallback=1"), "compat");
  assert.equal(resolveDigitalHumanMode("?embed=1"), "live");
});

test("pause toggles the real audio context instead of stopping queued speech", async () => {
  let state = "running";
  const player = new PcmStreamPlayer();
  player.context = {
    get state() { return state; },
    async suspend() { state = "suspended"; },
    async resume() { state = "running"; },
  };

  assert.equal(await player.togglePaused(), true);
  assert.equal(state, "suspended");
  assert.equal(await player.togglePaused(), false);
  assert.equal(state, "running");
});
