import test from "node:test";
import assert from "node:assert/strict";

import {
  isPlaybackShortcutTarget,
  startActionTimeline,
  advanceActionTimeline,
} from "../src/features/openmaic/playbackTimeline.js";

const plan = (steps = []) => ({ steps });
const scene = (actions = [], elementIds = ["title"]) => ({
  actions,
  content: { type: "slide", canvas: { elements: elementIds.map((id) => ({ id })) } },
});

test("keyboard playback leaves form fields and editable text alone", () => {
  for (const target of [
    { tagName: "INPUT" },
    { tagName: "TEXTAREA" },
    { tagName: "SELECT" },
    { tagName: "BUTTON", isContentEditable: true },
    { tagName: "DIV", closest: (selector) => selector.includes("[role=\"slider\"]") ? {} : null },
  ]) {
    assert.equal(isPlaybackShortcutTarget(target), true);
  }
  assert.equal(isPlaybackShortcutTarget({ tagName: "DIV", closest: () => null }), false);
});

test("timeline resolves steps by action id and only executes available element actions", () => {
  const current = startActionTimeline(plan([
    { action_id: "spot", type: "spotlight", mode: "fire_and_forget" },
    { action_id: "missing", type: "laser", mode: "fire_and_forget" },
    { action_id: "speech", type: "speech", mode: "sync" },
  ]), scene([
    { id: "spot", type: "spotlight", elementId: "title", dimOpacity: 0.4 },
    { id: "missing", type: "laser", elementId: "not-on-canvas" },
    { id: "speech", type: "speech", text: "真实的文字" },
  ]));

  assert.equal(current.status, "playing");
  const spotlight = advanceActionTimeline(current);
  assert.deepEqual(spotlight.effect, { kind: "spotlight", elementId: "title", options: { dimness: 0.4 } });

  const invalidTarget = advanceActionTimeline(spotlight.next);
  assert.equal(invalidTarget.skipped.reason, "element_not_found");

  const unsupported = advanceActionTimeline(invalidTarget.next);
  assert.deepEqual(unsupported.skipped, { actionId: "speech", type: "speech", reason: "client_runtime_unavailable" });
  assert.equal(unsupported.next.status, "completed");
});

test("pausing, restarting and changing scene cannot carry an old effect forward", () => {
  const running = startActionTimeline(plan([{ action_id: "laser", type: "laser", mode: "fire_and_forget" }]), scene([
    { id: "laser", type: "laser", elementId: "title", color: "#00ff88" },
  ]));
  const fired = advanceActionTimeline(running);
  assert.equal(fired.next.status, "completed");
  assert.equal(fired.effect.kind, "laser");

  const paused = startActionTimeline(plan([{ action_id: "laser", type: "laser", mode: "fire_and_forget" }]), scene([
    { id: "laser", type: "laser", elementId: "title" },
  ]), { paused: true });
  assert.equal(advanceActionTimeline(paused).effect, null);
  assert.equal(advanceActionTimeline(paused).next.status, "paused");

  const nextScene = startActionTimeline(plan(), scene());
  assert.equal(nextScene.status, "completed");
  assert.equal(nextScene.clearEffects, true);
});
