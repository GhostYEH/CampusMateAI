import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { clampVolume, createNoiseBuffer, volumeToGain } from "../src/features/study/whiteNoise.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const studyPage = readFileSync(resolve(root, "src/pages/StudyPage.jsx"), "utf8");
const control = readFileSync(resolve(root, "src/components/study/WhiteNoiseControl.jsx"), "utf8");
const styles = readFileSync(resolve(root, "src/styles.css"), "utf8");

test("study page includes a functional white-noise control in focus mode", () => {
  assert.match(studyPage, /WhiteNoiseControl/);
  assert.match(studyPage, /useWhiteNoise/);
  assert.match(control, /white-noise-control/);
});

test("white-noise control has the elastic slider visual contract", () => {
  assert.match(styles, /\.white-noise-control/);
  assert.match(styles, /\.elastic-slider/);
  assert.match(styles, /\.elastic-slider__range/);
});

test("white-noise volume is clamped and mapped to a gentle gain curve", () => {
  assert.equal(clampVolume(-5), 0);
  assert.equal(clampVolume(53.4), 53);
  assert.equal(clampVolume(120), 100);
  assert.equal(volumeToGain(0), 0);
  assert.ok(volumeToGain(70) < volumeToGain(100));
  assert.ok(volumeToGain(100) <= 0.24);
});

test("white-noise buffer fills a looping audio source with samples", () => {
  const context = {
    sampleRate: 10,
    createBuffer: (channels, frameCount, sampleRate) => {
      const channel = new Float32Array(frameCount);
      return { channels, frameCount, sampleRate, getChannelData: () => channel };
    },
  };
  const buffer = createNoiseBuffer(context, 2);
  assert.equal(buffer.frameCount, 20);
  assert.ok(buffer.getChannelData(0).some((sample) => sample !== 0));
});
