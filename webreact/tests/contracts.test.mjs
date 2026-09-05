import test from "node:test";
import assert from "node:assert/strict";
import { itemsOf, normalizeNotice, studySessionPayload, submissionPayload } from "../src/data/contracts.js";
import { formatDateTime, toDate } from "../src/utils/date.js";

test("itemsOf accepts both array and paginated responses", () => {
  const items = [{ id: "1" }];
  assert.deepEqual(itemsOf(items), items);
  assert.deepEqual(itemsOf({ items }), items);
  assert.deepEqual(itemsOf({ data: items }), []);
});

test("study session payload matches the backend state machine schema", () => {
  assert.deepEqual(studySessionPayload({ goal: "复习", mode: "deep", minutes: 50 }), {
    mode: "focus", experience_mode: "SMART_GUARD", planned_duration_seconds: 3000, goal: "复习",
  });
  assert.deepEqual(studySessionPayload({ goal: "阅读", mode: "quiet" }), {
    mode: "focus", experience_mode: "QUIET", goal: "阅读",
  });
});

test("submission payload preserves backend field names", () => {
  assert.deepEqual(submissionPayload("正文"), { text_content: "正文", submit: false });
  assert.deepEqual(submissionPayload("正文", true), { text_content: "正文", submit: true });
});

test("notice normalization uses the backend time and unread fields", () => {
  assert.deepEqual(normalizeNotice({ id: "n1", time: "2026-09-04T10:00:00Z", unread: true }), {
    id: "n1", time: "2026-09-04T10:00:00Z", unread: true, has_read: false, published_at: "2026-09-04T10:00:00Z", source: "",
  });
  assert.equal(normalizeNotice({ source_name: "学习通课程" }).source, "学习通课程");
});

test("date helpers accept ISO dates and Unix timestamps from external systems", () => {
  assert.equal(toDate("1783209663000")?.toISOString(), "2026-07-05T00:01:03.000Z");
  assert.equal(toDate("1783209663")?.toISOString(), "2026-07-05T00:01:03.000Z");
  assert.match(formatDateTime("1783209663000", { timeZone: "UTC", dateStyle: "medium", timeStyle: "short" }, "时间待定"), /2026/);
});

test("date helpers return the fallback instead of throwing for malformed values", () => {
  assert.equal(toDate("not-a-date"), null);
  assert.equal(formatDateTime("not-a-date", { dateStyle: "medium", timeStyle: "short" }, "时间待定"), "时间待定");
});
