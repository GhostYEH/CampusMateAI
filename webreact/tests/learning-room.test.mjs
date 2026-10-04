import test from "node:test";
import assert from "node:assert/strict";
import "./helpers/setup-globals.mjs";
import { client } from "../src/data/api.js";
import { createMockClient } from "./helpers/mock-client.mjs";
import { acceptLearningInvitation, createLearningRoom, getLearningArchive, getLearningMessages, inviteLearningStudent, sendLearningMessage } from "../src/data/learningRoomApi.js";
import { isLearningRoomMessage, learningSpaceEmbedUrl, LEARNING_ROOM_CHANNEL, mergeLearningMessages } from "../src/data/learningRoomBridge.js";

test("bridge requires both the approved origin and the actual iframe window", () => {
  const frame = {};
  const origin = "https://classroom.example.edu";
  const valid = { source: frame, origin, data: { channel: LEARNING_ROOM_CHANNEL, type: "entry" } };
  assert.equal(isLearningRoomMessage(valid, origin, frame), true);
  assert.equal(isLearningRoomMessage({ ...valid, source: {} }, origin, frame), false);
  assert.equal(isLearningRoomMessage({ ...valid, origin: "https://classroom.example.edu.evil.invalid" }, origin, frame), false);
  assert.equal(isLearningRoomMessage({ ...valid, data: { type: "entry" } }, origin, frame), false);
  assert.equal(isLearningRoomMessage(valid, origin, null), false);
  const url = new URL(learningSpaceEmbedUrl(origin, "https://campus.example.edu"));
  assert.equal(url.origin, origin);
  assert.equal(url.searchParams.get("campusmateOrigin"), "https://campus.example.edu");
  assert.equal(url.searchParams.has("access_token"), false);
});

test("overlapping message pages deduplicate by server ID and keep server order", () => {
  const merged = mergeLearningMessages([{ id: 7, content: "hello" }, { id: 9 }], [{ id: 9 }, { id: 8 }]);
  assert.deepEqual(merged.map((message) => message.id), [7, 8, 9]);
});

test("room API uploads the portable archive and uses scoped message cursors", async () => {
  const mock = createMockClient(client);
  const base = "/magicclass/learning-space";
  try {
    mock.onPost(`${base}/rooms`, { id: "room_test" });
    await createLearningRoom({ archive: new Blob(["archive"]), title: "同一节课", stageId: "stage_test" });
    const form = mock.lastRequest().data;
    assert.equal(form.get("title"), "同一节课");
    assert.equal(form.get("stage_id"), "stage_test");
    assert.equal(await form.get("file").text(), "archive");
    mock.onPost(`${base}/rooms/room_test/invitations`, { status: "pending" });
    await inviteLearningStudent("room_test", "usr_peer");
    assert.deepEqual(mock.lastRequest().data, { uid: "usr_peer" });
    mock.onPost(`${base}/invitations/room_test/accept`, { id: "room_test" });
    await acceptLearningInvitation("room_test");
    mock.onGet(`${base}/rooms/room_test/archive`, new Blob(["same archive"]));
    assert.equal(await (await getLearningArchive("room_test")).text(), "same archive");
    mock.onGet(`${base}/rooms/room_test/messages`, { items: [] });
    await getLearningMessages("room_test", 7);
    assert.equal(mock.lastRequest().params.after, 7);
    mock.onPost(`${base}/rooms/room_test/messages`, { id: 8 });
    await sendLearningMessage("room_test", "一起学", "message_test");
    assert.deepEqual(mock.lastRequest().data, { content: "一起学", client_id: "message_test" });
  } finally { mock.reset(); mock.clearTokens(); }
});
