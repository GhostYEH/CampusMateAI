import test from "node:test";
import assert from "node:assert/strict";

import { Pcm16Decoder, pcm16ToFloat32, rmsLevel } from "./pcmPlayer.js";
import { normalizeSpeechText } from "./speechText.js";
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
