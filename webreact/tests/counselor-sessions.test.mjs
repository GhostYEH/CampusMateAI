import test from "node:test";
import assert from "node:assert/strict";
import { counselorSessionsKey, readCounselorSessions, saveCounselorSessions } from "../src/data/counselorSessions.js";

function storage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
}

test("chat history is isolated by account and survives returning to its owner", () => {
  const saved = storage();
  const a = [{ id: "chat-a", messages: [{ role: "user", text: "private A" }] }];
  const b = [{ id: "chat-b", messages: [{ role: "user", text: "private B" }] }];
  saveCounselorSessions("a", a, saved);
  assert.deepEqual(readCounselorSessions("b", saved), []);
  saveCounselorSessions("b", b, saved);
  assert.deepEqual(readCounselorSessions("a", saved), a);
  assert.deepEqual(readCounselorSessions("b", saved), b);
});

test("unowned legacy history is never assigned to the next login", () => {
  const saved = storage();
  const legacy = JSON.stringify([{ id: "legacy", messages: ["private"] }]);
  saved.setItem("campus_counselor_sessions", legacy);
  assert.deepEqual(readCounselorSessions("next-user", saved), []);
  assert.equal(saved.getItem("campus_counselor_sessions"), legacy);
  saveCounselorSessions("anon", [{ id: "anonymous" }], saved);
  assert.deepEqual(readCounselorSessions("anon", saved), []);
});

test("invalid history payloads do not crash the page", () => {
  const saved = storage();
  for (const raw of ["{", "null", "{}", '[null,42,{"id":"valid"}]']) {
    saved.setItem(counselorSessionsKey("a"), raw);
    assert.deepEqual(readCounselorSessions("a", saved), raw.startsWith("[") ? [{ id: "valid" }] : []);
  }
});
