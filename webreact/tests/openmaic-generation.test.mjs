import assert from "node:assert/strict";
import test from "node:test";

import "./helpers/setup-globals.mjs";
import * as api from "../src/data/api.js";
import { createMockClient } from "./helpers/mock-client.mjs";

test("generation sends the selected mode, prompt, roster and stable idempotency key", async () => {
  const mock = createMockClient(api.default);
  mock.onPost("/courses/c1/workspaces/ws1/generate", { job: { id: "job1", status: "completed" }, stage_id: "stg1" }, 201);
  await api.generateOpenMAICStage("c1", "ws1", { mode: "quiz", prompt: "复习极限", idempotencyKey: "generate-1" });
  const request = mock.lastRequest();
  assert.deepEqual(request.data, { mode: "quiz", prompt: "复习极限", role_mode: "preset", selected_role_ids: [] });
  assert.equal(request.headers["Idempotency-Key"], "generate-1");
});

test("whiteboard writes carry both revision and idempotency headers", async () => {
  const mock = createMockClient(api.default);
  mock.onPost("/courses/c1/workspaces/ws1/stages/stg1/whiteboard", { revision: 2 });
  await api.addOpenMAICWhiteboard("c1", "ws1", "stg1", { board: { id: "b1", title: "草稿", elements: [] }, revision: 1, idempotencyKey: "board-1" });
  const request = mock.lastRequest();
  assert.equal(request.headers["If-Match"], "1");
  assert.equal(request.headers["Idempotency-Key"], "board-1");
  assert.deepEqual(request.data, { board: { id: "b1", title: "草稿", elements: [] } });
});

test("speech and discussion requests stay course-bound and idempotent", async () => {
  const mock = createMockClient(api.default);
  mock.onPost("/courses/c1/tts", { job_id: "tts-job", job: { status: "queued" } }, 202);
  await api.synthesizeOpenMAICTts("c1", { text: "讲解极限", voice: "苏打", idempotencyKey: "tts-1" });
  let request = mock.lastRequest();
  assert.equal(request.url, "/courses/c1/tts");
  assert.deepEqual(request.data, { text: "讲解极限", voice: "苏打" });
  assert.equal(request.headers["Idempotency-Key"], "tts-1");

  mock.reset();
  mock.onPost("/courses/c1/discussion", { job_id: "discussion-job", job: { status: "queued" } }, 202);
  await api.runOpenMAICDiscussion("c1", { prompt: "讨论极限的定义", idempotencyKey: "discussion-1" });
  request = mock.lastRequest();
  assert.equal(request.url, "/courses/c1/discussion");
  assert.deepEqual(request.data, { prompt: "讨论极限的定义" });
  assert.equal(request.headers["Idempotency-Key"], "discussion-1");
});

test("video export enqueues a render job through the authenticated gateway", async () => {
  const mock = createMockClient(api.default);
  mock.onPost("/courses/c1/workspaces/ws1/stages/stg1/export/video", { job_id: "video-job", job: { status: "queued" }, format: "mp4" }, 202);
  await api.enqueueOpenMAICStageVideo("c1", "ws1", "stg1", { idempotencyKey: "video-1" });
  const request = mock.lastRequest();
  assert.equal(request.url, "/courses/c1/workspaces/ws1/stages/stg1/export/video");
  assert.equal(request.headers["Idempotency-Key"], "video-1");
});

test("workspace provider tools are capability-gated and recover their artifact", async () => {
  const source = await import("node:fs").then(({ readFileSync }) => readFileSync(new URL("../src/components/openmaic/ProviderToolsPanel.jsx", import.meta.url), "utf8"));
  assert.match(source, /canTts/);
  assert.match(source, /canDiscussion/);
  assert.match(source, /getOpenMAICArtifact/);
  assert.match(source, /synthesizeOpenMAICTts/);
  assert.match(source, /runOpenMAICDiscussion/);
});

test("provider status uses the CampusMate route and does not need an exposed key", async () => {
  const mock = createMockClient(api.default);
  mock.onGet("/openmaic/fusion/providers", { state: "ready", providers: { llm: false, tts: false } });
  const status = await api.getOpenMAICProviderStatus();
  assert.equal(status.providers.tts, false);
  assert.equal(mock.lastRequest().url, "/openmaic/fusion/providers");
});

test("courses home fetches provider status independently from course content", async () => {
  const source = await import("node:fs").then(({ readFileSync }) => readFileSync(new URL("../src/pages/ParityPages.jsx", import.meta.url), "utf8"));
  assert.match(source, /api\.getOpenMAICProviderStatus\(\)/);
  assert.match(source, /providerStatus/);
});
