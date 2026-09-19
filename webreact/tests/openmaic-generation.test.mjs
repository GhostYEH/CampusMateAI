import assert from "node:assert/strict";
import test from "node:test";

import "./helpers/setup-globals.mjs";
import * as api from "../src/data/api.js";
import { createMockClient } from "./helpers/mock-client.mjs";

test("generation sends the selected mode, prompt and stable idempotency key", async () => {
  const mock = createMockClient(api.default);
  mock.onPost("/courses/c1/workspaces/ws1/generate", { job: { id: "job1", status: "completed" }, stage_id: "stg1" }, 201);
  await api.generateOpenMAICStage("c1", "ws1", { mode: "quiz", prompt: "复习极限", idempotencyKey: "generate-1" });
  const request = mock.lastRequest();
  assert.deepEqual(request.data, { mode: "quiz", prompt: "复习极限" });
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

test("provider status uses the CampusMate route and does not need an exposed key", async () => {
  const mock = createMockClient(api.default);
  mock.onGet("/openmaic/fusion/providers", { state: "ready", providers: { llm: false, tts: false } });
  const status = await api.getOpenMAICProviderStatus();
  assert.equal(status.providers.tts, false);
  assert.equal(mock.lastRequest().url, "/openmaic/fusion/providers");
});
