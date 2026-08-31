import assert from "node:assert/strict";
import test from "node:test";

import * as runtime from "../../../public/digital-human/mobileRuntime.js";

const {
  createSpeechEndpoint,
  createUnitySpeechMessage,
  normalizeRuntimeConfig,
  PcmStreamPlayer,
  resolveDigitalHumanMode,
  resolveMobileLayout,
} = runtime;

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

test("selects the full-bleed host layout for Android embeds and Harmony", () => {
  assert.equal(resolveMobileLayout("?layout=harmony"), "harmony");
  assert.equal(resolveMobileLayout("?embed=1"), "embed");
  assert.equal(resolveMobileLayout("?layout=android"), "default");
  assert.equal(resolveMobileLayout(""), "default");
});

test("compatibility mode skips the Unity renderer while preserving the audio host", () => {
  assert.equal(resolveDigitalHumanMode("?embed=1&fallback=1"), "compat");
  assert.equal(resolveDigitalHumanMode("?embed=1"), "live");
});

test("host and system reduced-motion preferences both disable avatar movement", () => {
  assert.equal(runtime.resolveReducedMotion("?reduceMotion=1", false), true);
  assert.equal(runtime.resolveReducedMotion("", true), true);
  assert.equal(runtime.resolveReducedMotion("", false), false);
});

test("speech levels are amplified enough for a clearly visible mouth shape", () => {
  assert.equal(runtime.emphasizeSpeechLevel(0), 0);
  assert.ok(runtime.emphasizeSpeechLevel(0.1) >= 0.35);
  assert.equal(runtime.emphasizeSpeechLevel(1), 1);
});

test("avatar motion keeps moving at idle and becomes livelier while speaking", () => {
  const idle = runtime.avatarMotionFrame(1_250, { speaking: false, speechLevel: 0 });
  const talking = runtime.avatarMotionFrame(1_250, { speaking: true, speechLevel: 0.7 });

  assert.ok(Math.abs(idle.rotateDeg) > 0.1);
  assert.ok(Math.abs(idle.translateYPercent) > 0.1);
  assert.ok(Math.abs(talking.rotateDeg) > Math.abs(idle.rotateDeg));
  assert.ok(talking.mouthOpen >= 0.7);
});

test("reduced motion preserves speech mouth movement but removes head motion", () => {
  const frame = runtime.avatarMotionFrame(1_250, {
    speaking: true,
    speechLevel: 0.7,
    reducedMotion: true,
  });

  assert.equal(frame.rotateDeg, 0);
  assert.equal(frame.translateYPercent, 0);
  assert.ok(frame.mouthOpen >= 0.7);
});

test("blink delays stay inside the natural idle window", () => {
  assert.equal(runtime.nextBlinkDelay(0), 2_800);
  assert.equal(runtime.nextBlinkDelay(1), 5_200);
});

test("compatibility animator writes idle, speech and blink state to the visible avatar", () => {
  let frameCallback = null;
  let cancelledFrame = null;
  const properties = new Map();
  const classes = new Set();
  const element = {
    style: { setProperty: (name, value) => properties.set(name, value) },
    classList: {
      toggle(name, enabled) {
        if (enabled) classes.add(name);
        else classes.delete(name);
      },
    },
  };
  const animator = new runtime.CompatAvatarAnimator(element, {
    now: () => 0,
    random: () => 0,
    requestFrame: (callback) => { frameCallback = callback; return 42; },
    cancelFrame: (id) => { cancelledFrame = id; },
  });

  animator.start();
  frameCallback(1_250);
  assert.notEqual(properties.get("--avatar-rotate"), "0deg");

  animator.setSpeaking(true);
  animator.setSpeechLevel(0.2);
  frameCallback(1_500);
  assert.equal(classes.has("speaking"), true);
  assert.ok(Number(properties.get("--mouth-open")) >= 0.5);

  frameCallback(2_800);
  frameCallback(2_880);
  assert.ok(Number(properties.get("--blink")) > 0.95);

  animator.stop();
  assert.equal(cancelledFrame, 42);
  assert.equal(properties.get("--mouth-open"), "0");
});

test("compatibility speech messages drive the visible avatar instead of being discarded", () => {
  const events = [];
  const animator = {
    setSpeaking: (value) => events.push(["speaking", value]),
    setSpeechLevel: (value) => events.push(["level", value]),
  };

  runtime.applyAvatarSpeechMessage(animator, "speech-state", true);
  runtime.applyAvatarSpeechMessage(animator, "speech-level", 0.25);
  runtime.applyAvatarSpeechMessage(animator, "speech-stop", true);

  assert.deepEqual(events, [
    ["speaking", true],
    ["level", 0.25],
    ["level", 0],
    ["speaking", false],
  ]);
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
