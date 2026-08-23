import test from "node:test";
import assert from "node:assert/strict";

import { Pcm16Decoder, pcm16ToFloat32, rmsLevel } from "./pcmPlayer.js";
import { normalizeSpeechText } from "./speechText.js";
import { DigitalHumanSpeechController } from "./speechController.js";
import { streamAssistantSpeech } from "./speechStream.js";
import { createUnityBridge } from "./unityBridge.js";


test("normalizes markdown into readable speech text", () => {
  const markdown = "## 提醒\n**你好**，[教务处](https://example.test)通知：`周一`办理。\n```js\nalert(1)\n```";

  assert.equal(normalizeSpeechText(markdown), "提醒 你好，教务处通知：周一办理。");
});


test("converts signed little-endian PCM16 samples", () => {
  const samples = pcm16ToFloat32(new Uint8Array([0xff, 0x7f, 0x00, 0x80, 0x00, 0x00]));

  assert.ok(samples[0] > 0.999);
  assert.equal(samples[1], -1);
  assert.equal(samples[2], 0);
  assert.ok(rmsLevel(samples) > 0.81 && rmsLevel(samples) < 0.82);
});


test("preserves a split PCM sample between network chunks", () => {
  const decoder = new Pcm16Decoder();

  assert.deepEqual([...decoder.push(new Uint8Array([0x00]))], []);
  const decoded = decoder.push(new Uint8Array([0x40, 0x00, 0xc0]));

  assert.deepEqual([...decoded], [0.5, -0.5]);
});


test("unity bridge clamps speech level and uses the current origin", () => {
  const sent = [];
  const iframe = {
    contentWindow: {
      postMessage(message, origin) {
        sent.push({ message, origin });
      },
    },
  };
  const bridge = createUnityBridge(iframe, "https://campus.example");

  bridge.setSpeechLevel(3);
  bridge.setSpeaking(true);
  bridge.stop();

  assert.deepEqual(sent, [
    { message: { source: "campusmate", type: "speech-level", value: 1 }, origin: "https://campus.example" },
    { message: { source: "campusmate", type: "speech-state", value: true }, origin: "https://campus.example" },
    { message: { source: "campusmate", type: "speech-stop", value: true }, origin: "https://campus.example" },
  ]);
});


test("speech stream posts authenticated text and yields every PCM chunk", async () => {
  const chunks = [new Uint8Array([1, 2]), new Uint8Array([3, 4])];
  const received = [];
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url, options });
    let index = 0;
    return {
      ok: true,
      status: 200,
      headers: new Headers({ "x-audio-sample-rate": "24000" }),
      body: { getReader: () => ({ read: async () => index < chunks.length ? { done: false, value: chunks[index++] } : { done: true } }) },
    };
  };

  await streamAssistantSpeech("你好", {
    baseUrl: "/api/v1",
    accessToken: "token-value",
    fetchImpl,
    onChunk: (chunk) => received.push([...chunk]),
  });

  assert.deepEqual(received, [[1, 2], [3, 4]]);
  assert.equal(calls[0].url, "/api/v1/assistant/tts");
  assert.equal(calls[0].options.headers.Authorization, "Bearer token-value");
  assert.equal(calls[0].options.body, JSON.stringify({ text: "你好" }));
});


test("speech controller finishes playback and reports non-abort failures", async () => {
  const events = [];
  const player = {
    append: async (chunk) => events.push(["append", ...chunk]),
    finish: () => events.push(["finish"]),
    stop: () => events.push(["stop"]),
  };
  const errors = [];
  const controller = new DigitalHumanSpeechController({
    player,
    streamSpeech: async (_text, { onChunk }) => onChunk(new Uint8Array([8, 9])),
    onError: (error) => errors.push(error.message),
  });

  assert.equal(await controller.speak("欢迎"), true);
  assert.deepEqual(events, [["stop"], ["append", 8, 9], ["finish"]]);
  assert.deepEqual(errors, []);

  controller.streamSpeech = async () => { throw new Error("provider unavailable"); };
  assert.equal(await controller.speak("重试"), false);
  assert.equal(errors.at(-1), "provider unavailable");
  assert.deepEqual(events.at(-1), ["stop"]);
});
