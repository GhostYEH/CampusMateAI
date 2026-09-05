import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { clearStoredSession, isAllowedSession, readStoredSession } from "../src/app/auth.js";

const appSource = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");

function storage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, String(value)); },
    removeItem(key) { values.delete(key); },
  };
}

test("readStoredSession rejects malformed or tokenless sessions", () => {
  const malformed = storage({ campus_session: "{" });
  assert.equal(readStoredSession(malformed), null);
  assert.equal(malformed.getItem("campus_session"), null);

  const tokenless = storage({ campus_session: JSON.stringify({ role: "student" }) });
  assert.equal(readStoredSession(tokenless), null);
});

test("isAllowedSession only accepts a student session with an access token", () => {
  assert.equal(isAllowedSession({ role: "student" }, "access"), true);
  assert.equal(isAllowedSession({ role: "teacher" }, "access"), false);
  assert.equal(isAllowedSession({ role: "student" }, ""), false);
  assert.equal(isAllowedSession(null, "access"), false);
});

test("clearStoredSession removes every auth key", () => {
  const saved = storage({
    campus_session: "session",
    campus_access_token: "access",
    campus_refresh_token: "refresh",
  });
  clearStoredSession(saved);
  assert.equal(saved.getItem("campus_session"), null);
  assert.equal(saved.getItem("campus_access_token"), null);
  assert.equal(saved.getItem("campus_refresh_token"), null);
});

test("route records preserve every Vue route family", () => {
  const paths = [
    "/login", "/", "/home", "/courses", "/courses/:courseId",
    "/tasks", "/tasks/:kind/:id", "/community", "/community/create",
    "/community/:postId", "/university", "/counselor", "/notifications",
    "/announcements/:announcementId", "/study", "/exams", "/exams/:examId",
    "/exams/:examId/edit", "/profile", "/profile/chaoxing",
    "/profile/academic", "/profile/settings", "/profile/:section",
  ];
  for (const path of paths) assert.ok(appSource.includes(`path="${path}"`), `missing route ${path}`);
});
