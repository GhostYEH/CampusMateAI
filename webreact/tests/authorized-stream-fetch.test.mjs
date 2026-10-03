import test from "node:test";
import assert from "node:assert/strict";
import axios from "axios";
import { createClient } from "../src/data/http/client.js";
import { chatStream, streamAssistantSpeech } from "../src/data/api.js";

function storage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, String(value)); },
    removeItem(key) { values.delete(key); },
  };
}

function streamResponse(status, chunks = [], headers = {}) {
  return new Response(new ReadableStream({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(new TextEncoder().encode(chunk)));
      controller.close();
    },
  }), { status, headers });
}

test("chat and TTS retry one 401 with refreshed authorization and preserve stream content", async () => {
  const saved = storage({ campus_access_token: "old-access", campus_refresh_token: "old-refresh" });
  const oldStorage = globalThis.localStorage;
  const oldFetch = globalThis.fetch;
  const oldAdapter = axios.defaults.adapter;
  const calls = [];
  globalThis.localStorage = saved;
  globalThis.fetch = async (url, init) => {
    const requestHeaders = new Headers(init.headers);
    calls.push({
      url,
      authorization: requestHeaders.get("Authorization"),
      contentType: requestHeaders.get("Content-Type"),
      accept: requestHeaders.get("Accept"),
    });
    if (url.endsWith("/counselor/chat") && calls.filter((call) => call.url === url).length === 1) return streamResponse(401);
    if (url.endsWith("/counselor/chat")) {
      return streamResponse(200, ['event: chunk\ndata: {"text":"hello"}\n\n', 'event: done\ndata: {}\n\n'], { "Content-Type": "text/event-stream" });
    }
    return streamResponse(200, ["audio bytes"], { "Content-Type": "audio/mpeg" });
  };
  axios.defaults.adapter = async (config) => {
    assert.equal(JSON.parse(config.data).refresh_token, "old-refresh");
    return { status: 200, data: { access_token: "new-access", refresh_token: "new-refresh" }, headers: {} };
  };
  try {
    const chunks = [];
    await chatStream("question", { onChunk: (chunk) => chunks.push(chunk) });
    const audio = [];
    await streamAssistantSpeech("hello", { onChunk: (chunk) => audio.push(new TextDecoder().decode(chunk)) });
    assert.deepEqual(chunks, ["hello"]);
    assert.deepEqual(audio, ["audio bytes"]);
    assert.equal(calls.length, 3);
    assert.deepEqual(calls.map((call) => call.authorization), [
      "Bearer old-access", "Bearer new-access", "Bearer new-access",
    ]);
    assert.ok(calls.every((call) => call.contentType === "application/json"));
    assert.equal(calls[0].accept, "text/event-stream");
    assert.equal(calls[2].accept, "application/octet-stream");
  } finally {
    globalThis.localStorage = oldStorage;
    globalThis.fetch = oldFetch;
    axios.defaults.adapter = oldAdapter;
  }
});

test("TTS retries its own 401 once and returns the retried audio stream", async () => {
  const saved = storage({ campus_access_token: "old-access", campus_refresh_token: "old-refresh" });
  const oldStorage = globalThis.localStorage;
  const oldFetch = globalThis.fetch;
  const oldAdapter = axios.defaults.adapter;
  const calls = [];
  globalThis.localStorage = saved;
  globalThis.fetch = async (url, init) => {
    calls.push({ url, authorization: new Headers(init.headers).get("Authorization") });
    if (calls.length === 1) return new Response(null, { status: 401 });
    return streamResponse(200, ["retried audio"]);
  };
  axios.defaults.adapter = async () => ({
    status: 200,
    data: { access_token: "new-access", refresh_token: "new-refresh" },
    headers: {},
  });
  try {
    const chunks = [];
    await streamAssistantSpeech("spoken text", { onChunk: (chunk) => chunks.push(new TextDecoder().decode(chunk)) });
    assert.deepEqual(chunks, ["retried audio"]);
    assert.deepEqual(calls.map((call) => call.authorization), ["Bearer old-access", "Bearer new-access"]);
  } finally {
    globalThis.localStorage = oldStorage;
    globalThis.fetch = oldFetch;
    axios.defaults.adapter = oldAdapter;
  }
});

test("concurrent Axios and fetch 401s share one refresh request", async () => {
  const saved = storage({ campus_access_token: "old-access", campus_refresh_token: "old-refresh" });
  const client = createClient("/api/v1", saved);
  const oldAdapter = axios.defaults.adapter;
  const oldFetch = globalThis.fetch;
  let releaseRefresh;
  let refreshCount = 0;
  axios.defaults.adapter = () => {
    refreshCount += 1;
    return new Promise((resolve) => { releaseRefresh = resolve; });
  };
  client.defaults.adapter = async (config) => {
    if (config.headers.get("Authorization") === "Bearer fresh-access") {
      return { config, status: 200, data: "ok", headers: {} };
    }
    throw { config, response: { status: 401, data: {}, config } };
  };
  let fetchCount = 0;
  globalThis.fetch = async (_url, init) => {
    fetchCount += 1;
    if (fetchCount === 1) return new Response(null, { status: 401 });
    assert.equal(new Headers(init.headers).get("Authorization"), "Bearer fresh-access");
    return new Response("ok", { status: 200 });
  };
  try {
    const axiosRequest = client.get("/protected");
    const fetchRequest = client.authorizedFetch("/stream");
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(refreshCount, 1);
    releaseRefresh({ status: 200, data: { access_token: "fresh-access", refresh_token: "fresh-refresh" }, headers: {} });
    await Promise.all([axiosRequest, fetchRequest]);
    assert.equal(refreshCount, 1);
    assert.equal(fetchCount, 2);
  } finally {
    axios.defaults.adapter = oldAdapter;
    globalThis.fetch = oldFetch;
  }
});

test("a fetch request with a late 401 replays only through the recorded refresh lineage", async () => {
  const saved = storage({ campus_access_token: "old-access", campus_refresh_token: "old-refresh", campus_session: "same-user" });
  const client = createClient("/api/v1", saved);
  const oldAdapter = axios.defaults.adapter;
  const oldFetch = globalThis.fetch;
  let releaseRefresh;
  let releaseLate401;
  let refreshes = 0;
  let requests = 0;
  axios.defaults.adapter = () => {
    refreshes += 1;
    return new Promise((resolve) => { releaseRefresh = resolve; });
  };
  globalThis.fetch = async (url, init) => {
    requests += 1;
    if (url === "/leader") return new Response(null, { status: 401 });
    if (requests === 2) return new Promise((resolve) => { releaseLate401 = () => resolve(new Response(null, { status: 401 })); });
    assert.equal(new Headers(init.headers).get("Authorization"), "Bearer next-access");
    return new Response("ok", { status: 200 });
  };
  try {
    const leader = client.authorizedFetch("/leader");
    const lateRequest = client.authorizedFetch("/late");
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(refreshes, 1);
    releaseRefresh({ status: 200, data: { access_token: "next-access", refresh_token: "next-refresh" }, headers: {} });
    assert.equal((await leader).status, 401); // retried once and still unauthorized
    releaseLate401();
    assert.equal((await lateRequest).status, 200);
    assert.equal(requests, 4);
    assert.equal(refreshes, 1);
    assert.equal(saved.getItem("campus_session"), "same-user");
  } finally {
    axios.defaults.adapter = oldAdapter;
    globalThis.fetch = oldFetch;
  }
});

test("an Axios request with a late 401 replays through the same successful refresh lineage", async () => {
  const saved = storage({ campus_access_token: "old-access", campus_refresh_token: "old-refresh" });
  const oldAdapter = axios.defaults.adapter;
  let releaseRefresh;
  let releaseLate401;
  let refreshes = 0;
  const sent = [];
  axios.defaults.adapter = (config) => {
    if (config.url.endsWith("/auth/refresh")) {
      refreshes += 1;
      return new Promise((resolve) => { releaseRefresh = () => resolve({ status: 200, data: { access_token: "next-access", refresh_token: "next-refresh" }, headers: {} }); });
    }
    throw new Error("data request must use the client adapter");
  };
  const client = createClient("/api/v1", saved);
  client.defaults.adapter = (config) => {
    sent.push({ url: config.url, authorization: config.headers.get("Authorization") });
    if (config.url.endsWith("/leader")) return Promise.reject({ config, response: { status: 401, data: {}, config } });
    if (sent.filter((item) => item.url.endsWith("/late")).length === 1) return new Promise((_, reject) => { releaseLate401 = () => reject({ config, response: { status: 401, data: {}, config } }); });
    return Promise.resolve({ config, status: 200, data: "ok", headers: {} });
  };
  try {
    const leader = client.get("/leader");
    const late = client.get("/late");
    await new Promise((resolve) => setImmediate(resolve));
    releaseRefresh();
    await assert.rejects(leader, (error) => error.response?.status === 401);
    releaseLate401();
    assert.equal((await late).data, "ok");
    assert.deepEqual(sent.filter((item) => item.url.endsWith("/late")).map((item) => item.authorization), [
      "Bearer old-access", "Bearer next-access",
    ]);
    assert.equal(refreshes, 1);
  } finally { axios.defaults.adapter = oldAdapter; }
});

test("Axios retry interceptor refuses a session changed before retry dispatch", async () => {
  const saved = storage({ campus_access_token: "old-access", campus_refresh_token: "old-refresh" });
  const oldAdapter = axios.defaults.adapter;
  let protectedRequests = 0;
  axios.defaults.adapter = async () => ({
    status: 200,
    data: { access_token: "refreshed-access", refresh_token: "refreshed-refresh" },
    headers: {},
  });
  const client = createClient("/api/v1", saved);
  client.defaults.adapter = async (config) => {
    protectedRequests += 1;
    throw { config, response: { status: 401, data: {}, config } };
  };
  client.interceptors.request.use(async (config) => {
    if (config._retried) {
      await Promise.resolve();
      saved.setItem("campus_access_token", "new-login-access");
      saved.setItem("campus_refresh_token", "new-login-refresh");
    }
    return config;
  });
  try {
    await assert.rejects(client.get("/protected"), /登录状态已变更/);
    assert.equal(protectedRequests, 1);
    assert.equal(saved.getItem("campus_access_token"), "new-login-access");
    assert.equal(saved.getItem("campus_refresh_token"), "new-login-refresh");
  } finally { axios.defaults.adapter = oldAdapter; }
});

test("a late old-token 401 does not replay after new login, regardless of unchanged session metadata", async () => {
  for (const replacement of [
    { access: "second-access", refresh: "second-refresh" },
  { access: "third-access", refresh: "third-refresh" },
  ]) {
    const saved = storage({ campus_access_token: "first-access", campus_refresh_token: "first-refresh", campus_session: "user" });
    const oldAdapter = axios.defaults.adapter;
    const oldFetch = globalThis.fetch;
    let releaseRefresh;
    let releaseLate401;
    let lateCalls = 0;
    axios.defaults.adapter = () => new Promise((resolve) => { releaseRefresh = resolve; });
    globalThis.fetch = async (url) => {
      if (url === "/leader") return new Response(null, { status: 401 });
      lateCalls += 1;
      return new Promise((resolve) => { releaseLate401 = () => resolve(new Response(null, { status: 401 })); });
    };
    const client = createClient("/api/v1", saved);
    try {
      const leader = client.authorizedFetch("/leader");
      const late = client.authorizedFetch("/late");
      await new Promise((resolve) => setImmediate(resolve));
      releaseRefresh({ status: 200, data: { access_token: "rotated-access", refresh_token: "rotated-refresh" }, headers: {} });
      await leader;
      saved.setItem("campus_access_token", replacement.access);
      saved.setItem("campus_refresh_token", replacement.refresh);
      // Same session metadata cannot establish lineage for a new token pair.
      releaseLate401();
      assert.equal((await late).status, 401);
      assert.equal(lateCalls, 1);
      assert.equal(saved.getItem("campus_access_token"), replacement.access);
      assert.equal(saved.getItem("campus_refresh_token"), replacement.refresh);
    } finally {
      axios.defaults.adapter = oldAdapter;
      globalThis.fetch = oldFetch;
    }
  }
});

test("a session change while fetch waits for refresh prevents replay and preserves new tokens", async () => {
  const saved = storage({ campus_access_token: "old-access", campus_refresh_token: "old-refresh" });
  const client = createClient("/api/v1", saved);
  const oldAdapter = axios.defaults.adapter;
  const oldFetch = globalThis.fetch;
  let releaseRefresh;
  let requests = 0;
  axios.defaults.adapter = () => new Promise((resolve) => { releaseRefresh = resolve; });
  globalThis.fetch = async () => { requests += 1; return new Response(null, { status: 401 }); };
  try {
    const pending = client.authorizedFetch("/stream");
    await new Promise((resolve) => setImmediate(resolve));
    saved.setItem("campus_access_token", "new-user-access");
    saved.setItem("campus_refresh_token", "new-user-refresh");
    releaseRefresh({ status: 200, data: { access_token: "stale-access", refresh_token: "stale-refresh" }, headers: {} });
    await assert.rejects(pending, /登录状态已变更/);
    assert.equal(requests, 1);
    assert.equal(saved.getItem("campus_access_token"), "new-user-access");
    assert.equal(saved.getItem("campus_refresh_token"), "new-user-refresh");
  } finally {
    axios.defaults.adapter = oldAdapter;
    globalThis.fetch = oldFetch;
  }
});

test("a repeated 401 is returned after one retry and one refresh", async () => {
  const saved = storage({ campus_access_token: "old-access", campus_refresh_token: "old-refresh" });
  const client = createClient("/api/v1", saved);
  const oldAdapter = axios.defaults.adapter;
  const oldFetch = globalThis.fetch;
  let refreshes = 0;
  let requests = 0;
  axios.defaults.adapter = async () => {
    refreshes += 1;
    return { status: 200, data: { access_token: "new-access", refresh_token: "new-refresh" }, headers: {} };
  };
  globalThis.fetch = async () => { requests += 1; return new Response(null, { status: 401 }); };
  try {
    const response = await client.authorizedFetch("/still-unauthorized");
    assert.equal(response.status, 401);
    assert.equal(requests, 2);
    assert.equal(refreshes, 1);
  } finally {
    axios.defaults.adapter = oldAdapter;
    globalThis.fetch = oldFetch;
  }
});

test("a failed in-flight fetch refresh cannot clear a logged-in replacement session", async () => {
  const saved = storage({ campus_access_token: "old-access", campus_refresh_token: "old-refresh" });
  const client = createClient("/api/v1", saved);
  const oldAdapter = axios.defaults.adapter;
  const oldFetch = globalThis.fetch;
  let rejectRefresh;
  let requests = 0;
  axios.defaults.adapter = () => new Promise((_, reject) => { rejectRefresh = reject; });
  globalThis.fetch = async () => { requests += 1; return new Response(null, { status: 401 }); };
  try {
    const pending = client.authorizedFetch("/stream");
    await new Promise((resolve) => setImmediate(resolve));
    saved.setItem("campus_access_token", "new-user-access");
    saved.setItem("campus_refresh_token", "new-user-refresh");
    rejectRefresh({ response: { status: 401 } });
    await assert.rejects(pending, /登录状态已变更/);
    assert.equal(requests, 1);
    assert.equal(saved.getItem("campus_access_token"), "new-user-access");
    assert.equal(saved.getItem("campus_refresh_token"), "new-user-refresh");
  } finally {
    axios.defaults.adapter = oldAdapter;
    globalThis.fetch = oldFetch;
  }
});

test("aborting during refresh prevents replay while stream body can outlive headers", async () => {
  const saved = storage({ campus_access_token: "old-access", campus_refresh_token: "old-refresh" });
  const client = createClient("/api/v1", saved);
  const oldAdapter = axios.defaults.adapter;
  const oldFetch = globalThis.fetch;
  let releaseRefresh;
  let requests = 0;
  axios.defaults.adapter = () => new Promise((resolve) => { releaseRefresh = resolve; });
  globalThis.fetch = async (_url, init) => {
    requests += 1;
    if (requests === 1) return new Response(null, { status: 401 });
    if (init.signal) assert.equal(init.signal.aborted, false);
    return new Response(new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("first"));
        setTimeout(() => { controller.enqueue(new TextEncoder().encode("second")); controller.close(); }, 50);
      },
    }), { status: 200 });
  };
  try {
    const controller = new AbortController();
    const pending = client.authorizedFetch("/stream", { signal: controller.signal });
    await new Promise((resolve) => setImmediate(resolve));
    controller.abort();
    releaseRefresh({ status: 200, data: { access_token: "fresh-access", refresh_token: "fresh-refresh" }, headers: {} });
    await assert.rejects(pending, { name: "AbortError" });
    assert.equal(requests, 1);

    const longStream = await client.authorizedFetch("/long-stream");
    const reader = longStream.body.getReader();
    const parts = [await reader.read(), await reader.read(), await reader.read()];
    assert.deepEqual(parts.map(({ value }) => value ? new TextDecoder().decode(value) : null), ["first", "second", null]);
  } finally {
    axios.defaults.adapter = oldAdapter;
    globalThis.fetch = oldFetch;
  }
});

test("authorized stream fetch does not impose a headers timeout on the response body", async () => {
  const saved = storage({ campus_access_token: "access", campus_refresh_token: "refresh" });
  const client = createClient("/api/v1", saved);
  const oldFetch = globalThis.fetch;
  let receivedInit;
  let response;
  globalThis.fetch = async (_url, init) => {
    receivedInit = init;
    return new Response(new ReadableStream({ start() {} }), { status: 200 });
  };
  try {
    response = await client.authorizedFetch("/open-ended-stream", {
      headers: { "Last-Event-ID": "event-42", Accept: "text/event-stream" },
    });
    assert.equal(response.status, 200);
    assert.equal(receivedInit.timeout, undefined);
    assert.equal(receivedInit.signal, undefined);
    assert.equal(new Headers(receivedInit.headers).get("Last-Event-ID"), "event-42");
    assert.equal(new Headers(receivedInit.headers).get("Accept"), "text/event-stream");
  } finally {
    await response?.body?.cancel();
    globalThis.fetch = oldFetch;
  }
});
