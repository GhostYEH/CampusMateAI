import test from "node:test";
import assert from "node:assert/strict";
import "./helpers/setup-globals.mjs";
import { client } from "../src/data/api.js";
import { createMockClient } from "./helpers/mock-client.mjs";
import {
  createStudyRoom, getStudyRoom, getStudyRoomMessages, sendStudyRoomMessage,
  updateStudyRoomState, controlStudyRoomTimer, mergeStudyRoomMessages,
} from "../src/data/studyRoomApi.js";

test("study room API posts the documented create body and reads with scoped cursor", async () => {
  const mock = createMockClient(client);
  const base = "/study/rooms";
  try {
    mock.onPost(`${base}/`, { id: "examroom_test", title: "冲刺" });
    await createStudyRoom({ title: "冲刺", focusMinutes: 30, breakMinutes: 10 });
    assert.deepEqual(mock.lastRequest().data, { title: "冲刺", focus_minutes: 30, break_minutes: 10 });

    mock.onGet(`${base}/examroom_test`, { id: "examroom_test", timer: { phase: "idle" } });
    await getStudyRoom("examroom_test");
    assert.equal(mock.lastRequest().url, `${base}/examroom_test`);

    mock.onGet(`${base}/examroom_test/messages`, { items: [] });
    await getStudyRoomMessages("examroom_test", 42);
    assert.equal(mock.lastRequest().params.after, 42);

    mock.onPost(`${base}/examroom_test/messages`, { id: 7 });
    await sendStudyRoomMessage("examroom_test", "一起加油", "c-1");
    assert.deepEqual(mock.lastRequest().data, { content: "一起加油", client_id: "c-1" });

    mock.onPatch(`${base}/examroom_test/state`, null, 204);
    await updateStudyRoomState("examroom_test", "focus", "刷题");
    assert.deepEqual(mock.lastRequest().data, { study_state: "focus", status_message: "刷题" });

    mock.onPost(`${base}/examroom_test/timer`, { timer: { phase: "focus" } });
    await controlStudyRoomTimer("examroom_test", "start_focus");
    assert.deepEqual(mock.lastRequest().data, { action: "start_focus" });
  } finally { mock.reset(); mock.clearTokens(); }
});

test("overlapping message pages deduplicate by server id and keep ascending order", () => {
  const merged = mergeStudyRoomMessages([{ id: 3, content: "a" }, { id: 5 }], [{ id: 5 }, { id: 4 }]);
  assert.deepEqual(merged.map((m) => m.id), [3, 4, 5]);
});
