import test from "node:test";
import assert from "node:assert/strict";
import { assignmentHasEnded, enterAssignmentReview, loadEndedAssignments } from "../src/features/magicclass/assignmentReviewModel.js";

const result = (status) => ({ course_id: "course", workspace_id: "review", job: { id: "job", status, progress: 10 } });
const options = () => ({ signal: new AbortController().signal, onPhase() {}, wait: async () => {} });

test("ended list reads all pages, includes missed assignments and excludes future, unknown and deleted tasks", async () => {
  const calls = [];
  const tasks = await loadEndedAssignments(async (params) => {
    calls.push(params);
    return params.page === 1 ? { has_more: true, items: [
      { id: "personal", status: "completed", source: "manual" },
      { id: "pending", status: "pending", source: "chaoxing", deadline: "2000-01-02T08:00:00Z" },
      { id: "old", status: "completed", source: "chaoxing", deadline: "2000-01-01T08:00:00Z" },
    ] } : { has_more: false, items: [
      { id: "new", status: "completed", source: "chaoxing", deadline: "2000-01-03T08:00:00Z" },
      { id: "future", status: "completed", source: "chaoxing", deadline: "2999-01-01T08:00:00Z" },
      { id: "unknown", status: "completed", source: "chaoxing" },
      { id: "deleted", status: "completed", source: "chaoxing", deleted_at: "2026-10-15" },
    ] };
  });
  assert.deepEqual(tasks.map((task) => task.id), ["new", "pending", "old"]);
  assert.deepEqual(calls, [1, 2].map((page) => ({ page, page_size: 200 })));
});

test("cutoff includes equality and treats China date-only deadlines as end of day", () => {
  assert.equal(assignmentHasEnded({ deadline: "2026-10-18" }, Date.parse("2026-10-18T15:59:58Z")), false);
  assert.equal(assignmentHasEnded({ deadline: "2026-10-18" }, Date.parse("2026-10-18T15:59:59Z")), true);
  assert.equal(assignmentHasEnded({ deadline: "2026-10-18T20:00:00" }, Date.parse("2026-10-18T12:00:00Z")), true);
  assert.equal(assignmentHasEnded({ deadline: "invalid" }), false);
});

test("one click waits for real job completion before returning the playback address", async () => {
  const phases = [], calls = [];
  const href = await enterAssignmentReview("work", {
    generateChaoxingAssignmentClassroom: async (id) => { calls.push(id); return result("queued"); },
    getMagicClassJob: async (...args) => { calls.push(args); return { id: "job", status: "completed" }; },
  }, { ...options(), onPhase: (phase) => phases.push(phase) });
  assert.equal(href, "/courses/course/workspaces/review?mode=playback");
  assert.deepEqual(calls, ["work", ["course", "job"]]);
  assert.deepEqual(phases, [{ state: "generating", progress: 10 }]);
});

test("a missing submitted snapshot is synchronized once before resuming the same assignment", async () => {
  const calls = [];
  let attempts = 0;
  const href = await enterAssignmentReview("work", {
    generateChaoxingAssignmentClassroom: async (id) => {
      calls.push(id); attempts += 1;
      if (attempts === 1) throw { response: { data: { message: "assignment_content_not_current" } } };
      return result("completed");
    },
    syncChaoxing: async () => calls.push("sync"),
  }, options());
  assert.equal(href, "/courses/course/workspaces/review?mode=playback");
  assert.deepEqual(calls, ["work", "sync", "work"]);
});

test("failed generation reuses the job retry endpoint and does not loop retries after another failure", async () => {
  const calls = [];
  await assert.rejects(enterAssignmentReview("work", {
    generateChaoxingAssignmentClassroom: async () => result("failed"),
    retryMagicClassJob: async (...args) => { calls.push(args); return { id: "job", status: "queued" }; },
    getMagicClassJob: async () => ({ id: "job", status: "failed" }),
  }, options()), /再次点击重试/);
  assert.deepEqual(calls, [["course", "job"]]);
});

test("leaving the page ignores an in-flight generation response and never starts polling", async () => {
  const controller = new AbortController();
  let resolve;
  const pending = new Promise((done) => { resolve = done; });
  const entering = enterAssignmentReview("work", {
    generateChaoxingAssignmentClassroom: () => pending,
    getMagicClassJob: () => assert.fail("must not poll after leaving"),
  }, { ...options(), signal: controller.signal });
  controller.abort(); resolve(result("queued"));
  assert.equal(await entering, null);
});
