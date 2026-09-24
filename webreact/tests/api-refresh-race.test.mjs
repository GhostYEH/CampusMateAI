import test from "node:test";
import assert from "node:assert/strict";
import axios from "axios";
import { createClient, refreshAccessToken } from "../src/data/api.js";

function storage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, String(value)); },
    removeItem(key) { values.delete(key); },
  };
}

test("refreshAccessToken stores a rotated token pair when the session is unchanged", async () => {
  const saved = storage({ campus_refresh_token: "old-refresh" });
  const previousAdapter = axios.defaults.adapter;
  axios.defaults.adapter = async () => ({
    status: 200,
    data: { access_token: "new-access", refresh_token: "new-refresh" },
    headers: {},
  });

  try {
    const access = await refreshAccessToken("/api/v1", saved);
    assert.equal(access, "new-access");
    assert.equal(saved.getItem("campus_access_token"), "new-access");
    assert.equal(saved.getItem("campus_refresh_token"), "new-refresh");
  } finally {
    axios.defaults.adapter = previousAdapter;
  }
});

test("a 401 refreshes and retries the original request once", async () => {
  const saved = storage({ campus_access_token: "old-access", campus_refresh_token: "old-refresh" });
  const client = createClient("/api/v1", saved);
  const previousAdapter = axios.defaults.adapter;
  const sentTokens = [];
  axios.defaults.adapter = async (config) => {
    assert.equal(JSON.parse(config.data).refresh_token, "old-refresh");
    return {
      status: 200,
      data: { access_token: "new-access", refresh_token: "new-refresh" },
      headers: {},
    };
  };
  client.defaults.adapter = (config) => {
    sentTokens.push(config.headers.get("Authorization"));
    if (sentTokens.length === 1) {
      return Promise.reject({ config, response: { status: 401, data: {}, config } });
    }
    return Promise.resolve({ config, status: 200, data: "ok", headers: {} });
  };

  try {
    assert.equal((await client.get("/private")).data, "ok");
    assert.deepEqual(sentTokens, ["Bearer old-access", "Bearer new-access"]);
  } finally {
    axios.defaults.adapter = previousAdapter;
  }
});

test("a late refresh response cannot overwrite a newer session", async () => {
  const saved = storage({ campus_refresh_token: "old-refresh" });
  const previousAdapter = axios.defaults.adapter;
  let resolveRequest;
  axios.defaults.adapter = () => new Promise((resolve) => { resolveRequest = resolve; });

  try {
    const pending = refreshAccessToken("/api/v1", saved);
    saved.setItem("campus_access_token", "current-access");
    saved.setItem("campus_refresh_token", "current-refresh");
    resolveRequest({
      status: 200,
      data: { access_token: "stale-access", refresh_token: "stale-refresh" },
      headers: {},
    });

    await assert.rejects(pending, /登录状态已变更/);
    assert.equal(saved.getItem("campus_access_token"), "current-access");
    assert.equal(saved.getItem("campus_refresh_token"), "current-refresh");
  } finally {
    axios.defaults.adapter = previousAdapter;
  }
});

test("a late refresh response cannot restore a logged-out session", async () => {
  const saved = storage({ campus_access_token: "old-access", campus_refresh_token: "old-refresh" });
  const previousAdapter = axios.defaults.adapter;
  let resolveRequest;
  axios.defaults.adapter = () => new Promise((resolve) => { resolveRequest = resolve; });

  try {
    const pending = refreshAccessToken("/api/v1", saved);
    saved.removeItem("campus_access_token");
    saved.removeItem("campus_refresh_token");
    resolveRequest({
      status: 200,
      data: { access_token: "stale-access", refresh_token: "stale-refresh" },
      headers: {},
    });

    await assert.rejects(pending, /登录状态已变更/);
    assert.equal(saved.getItem("campus_access_token"), null);
    assert.equal(saved.getItem("campus_refresh_token"), null);
  } finally {
    axios.defaults.adapter = previousAdapter;
  }
});

test("a failed refresh cannot clear a newer session", async () => {
  const saved = storage({ campus_refresh_token: "old-refresh" });
  const previousAdapter = axios.defaults.adapter;
  let rejectRequest;
  axios.defaults.adapter = () => new Promise((_, reject) => { rejectRequest = reject; });

  try {
    const pending = refreshAccessToken("/api/v1", saved);
    saved.setItem("campus_access_token", "current-access");
    saved.setItem("campus_refresh_token", "current-refresh");
    rejectRequest(new Error("network down"));

    await assert.rejects(pending, /登录状态已变更/);
    assert.equal(saved.getItem("campus_access_token"), "current-access");
    assert.equal(saved.getItem("campus_refresh_token"), "current-refresh");
  } finally {
    axios.defaults.adapter = previousAdapter;
  }
});

test("an old request's 401 is never replayed with a newer account's token", async () => {
  const saved = storage({ campus_access_token: "old-access", campus_refresh_token: "old-refresh" });
  const client = createClient("/api/v1", saved);
  let requests = 0;
  client.defaults.adapter = async (config) => {
    requests += 1;
    assert.equal(config.headers.get("Authorization"), "Bearer old-access");
    saved.setItem("campus_access_token", "current-access");
    saved.setItem("campus_refresh_token", "current-refresh");
    throw { config, response: { status: 401, data: {}, config } };
  };

  await assert.rejects(client.get("/private"), (error) => error.response?.status === 401);
  assert.equal(requests, 1);
  assert.equal(saved.getItem("campus_access_token"), "current-access");
  assert.equal(saved.getItem("campus_refresh_token"), "current-refresh");
});

test("a new account starts its own refresh while the old one is in flight", async () => {
  const saved = storage({ campus_access_token: "old-access", campus_refresh_token: "old-refresh" });
  const client = createClient("/api/v1", saved);
  const previousAdapter = axios.defaults.adapter;
  const refreshes = [];
  axios.defaults.adapter = (config) => new Promise((resolve) => {
    refreshes.push({ token: JSON.parse(config.data).refresh_token, resolve });
  });
  client.defaults.adapter = (config) => {
    if (config.headers.get("Authorization") === "Bearer new-access") {
      return Promise.resolve({ config, status: 200, data: "new-account-data", headers: {} });
    }
    return Promise.reject({ config, response: { status: 401, data: {}, config } });
  };

  try {
    const oldRequest = client.get("/private");
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(refreshes[0]?.token, "old-refresh");

    saved.setItem("campus_access_token", "current-access");
    saved.setItem("campus_refresh_token", "current-refresh");
    const newRequest = client.get("/private");
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(refreshes[1]?.token, "current-refresh");

    refreshes[1].resolve({
      status: 200, data: { access_token: "new-access", refresh_token: "new-refresh" }, headers: {},
    });
    assert.equal((await newRequest).data, "new-account-data");

    refreshes[0].resolve({
      status: 200, data: { access_token: "stale-access", refresh_token: "stale-refresh" }, headers: {},
    });
    await assert.rejects(oldRequest, /登录状态已变更/);
    assert.equal(saved.getItem("campus_refresh_token"), "new-refresh");
  } finally {
    axios.defaults.adapter = previousAdapter;
  }
});
