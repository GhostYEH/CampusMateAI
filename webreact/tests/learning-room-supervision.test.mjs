import test from "node:test";
import assert from "node:assert/strict";
import "./helpers/setup-globals.mjs";
import { client } from "../src/data/api.js";
import { createMockClient } from "./helpers/mock-client.mjs";
import {
  getLearningSupervision, reportLearningAttention, sendLearningNudge,
} from "../src/data/learningRoomApi.js";
import {
  attentionLabel, attentionSignal, mergeSupervisionNudge, pickFreshNudge,
} from "../src/data/learningRoomSupervision.js";

test("page visibility maps to a coarse, non-camera attention signal", () => {
  assert.equal(attentionSignal({ hidden: false, hiddenForMs: 0, idleForMs: 10_000 }), "FOCUSED");
  assert.equal(attentionSignal({ hidden: false, hiddenForMs: 0, idleForMs: 200_000 }), "POSSIBLY_DISTRACTED");
  assert.equal(attentionSignal({ hidden: true, hiddenForMs: 20_000, idleForMs: 0 }), "POSSIBLY_DISTRACTED");
  assert.equal(attentionSignal({ hidden: true, hiddenForMs: 80_000, idleForMs: 0 }), "AWAY");
  assert.equal(attentionSignal({ hidden: false, hiddenForMs: 0, idleForMs: 120_000 }), "UNKNOWN");
  assert.equal(attentionLabel("AWAY"), "暂时离开");
});

test("first supervision poll only records the cursor; later polls surface addressed nudges", () => {
  const history = [{ id: 3, target_uid: "usr_peer" }, { id: 4, target_uid: null }];
  const first = pickFreshNudge({ nudges: history, after: 0, meUid: "usr_me", initialized: false });
  assert.equal(first.nudge, null);
  assert.equal(first.newest, 4);
  const later = pickFreshNudge({
    nudges: [{ id: 5, target_uid: "usr_peer" }, { id: 6, target_uid: "usr_me" }],
    after: 4,
    meUid: "usr_me",
    initialized: true,
  });
  assert.equal(later.nudge.id, 6);
  assert.equal(later.newest, 6);
  const ownBroadcast = pickFreshNudge({
    nudges: [{ id: 8, target_uid: null, from_uid: "usr_me", kind: "HOST" }],
    after: 6,
    meUid: "usr_me",
    initialized: true,
  });
  assert.equal(ownBroadcast.nudge, null);
  assert.equal(ownBroadcast.newest, 8);
  assert.equal(mergeSupervisionNudge({ id: 6 }, { id: 5 }).id, 6);
  assert.equal(mergeSupervisionNudge(null, { id: 7 }).id, 7);
});

test("supervision API uses scoped cursor and coarse states", async () => {
  const mock = createMockClient(client);
  const base = "/magicclass/learning-space/rooms/room_test";
  try {
    mock.onPut(`${base}/attention`, { state: "POSSIBLY_DISTRACTED", updated_at: "2026-10-05T00:00:00+00:00", teacher_reminder: null });
    await reportLearningAttention("room_test", "POSSIBLY_DISTRACTED", "PAGE_VISIBILITY");
    assert.deepEqual(mock.lastRequest().data, { state: "POSSIBLY_DISTRACTED", source: "PAGE_VISIBILITY" });

    mock.onGet(`${base}/supervision`, { me: { uid: "usr_me", state: "FOCUSED" }, members: [], stats: null, teacher_summary: null, teacher_name: "小伴老师", nudges: [] });
    await getLearningSupervision("room_test", 12);
    assert.equal(mock.lastRequest().params.after, 12);

    mock.onPost(`${base}/nudges`, { id: 13, target_uid: "usr_peer", kind: "HOST", content: "看回课件" });
    await sendLearningNudge("room_test", "usr_peer");
    assert.deepEqual(mock.lastRequest().data, { target_uid: "usr_peer", content: null });
    await sendLearningNudge("room_test", null, "同学们，继续听课");
    assert.deepEqual(mock.lastRequest().data, { target_uid: null, content: "同学们，继续听课" });
  } finally { mock.reset(); mock.clearTokens(); }
});
