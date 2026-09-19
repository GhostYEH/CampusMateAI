/**
 * Shared mock axios adapter for learner-state contract tests.
 * The caller must import setup-globals.mjs FIRST, then api.js, then this helper.
 */
import axios from "axios";
import { _store } from "./setup-globals.mjs";

/**
 * Install a mock adapter on the real client and global axios.
 * @param {object} client - the real axios client singleton from api.js
 * Returns an API to configure handlers and inspect recorded requests.
 */
export function createMockClient(client) {
  const requests = [];
  const handlers = new Map();

  function mockAdapter(config) {
    const recorded = {
      method: (config.method || "get").toLowerCase(),
      url: config.url,
      params: config.params || {},
      data: typeof config.data === "string" && config.data ? JSON.parse(config.data) : config.data,
      headers: { ...config.headers },
    };
    requests.push(recorded);

    const key = `${recorded.method}:${recorded.url}`;
    const handler = handlers.get(key);
    if (handler) return handler(config);

    return Promise.reject({
      config,
      response: { status: 404, data: { code: "NOT_MOCKED", message: `No mock for ${key}` }, config },
    });
  }

  client.defaults.adapter = mockAdapter;
  axios.defaults.adapter = mockAdapter;

  const api = {
    requests,

    onGet(url, data, status = 200) {
      handlers.set(`get:${url}`, (config) =>
        Promise.resolve({ status, data, config: config || {}, headers: {} }));
      return api;
    },

    onPost(url, data, status = 200) {
      handlers.set(`post:${url}`, (config) =>
        Promise.resolve({ status, data, config: config || {}, headers: {} }));
      return api;
    },

    onPut(url, data, status = 200) {
      handlers.set(`put:${url}`, (config) =>
        Promise.resolve({ status, data, config: config || {}, headers: {} }));
      return api;
    },

    onPatch(url, data, status = 200) {
      handlers.set(`patch:${url}`, (config) =>
        Promise.resolve({ status, data, config: config || {}, headers: {} }));
      return api;
    },

    onDelete(url, data, status = 200) {
      handlers.set(`delete:${url}`, (config) =>
        Promise.resolve({ status, data, config: config || {}, headers: {} }));
      return api;
    },

    onError(method, url, status, data) {
      handlers.set(`${method}:${url}`, (config) =>
        Promise.reject({ config: config || {}, response: { status, data, config: config || {} } }));
      return api;
    },

    /** Sequence of responses for the same endpoint (e.g. 401 then 200) */
    onSequence(method, url, responses) {
      let i = 0;
      handlers.set(`${method}:${url}`, (config) => {
        const r = responses[i++] || responses[responses.length - 1];
        if (r.error) {
          return Promise.reject({ config: config || {}, response: { status: r.status, data: r.data, config: config || {} } });
        }
        return Promise.resolve({ status: r.status || 200, data: r.data, config: config || {}, headers: {} });
      });
      return api;
    },

    reset() {
      requests.length = 0;
      handlers.clear();
    },

    setTokens(accessToken, refreshToken) {
      if (accessToken) _store.set("campus_access_token", accessToken);
      else _store.delete("campus_access_token");
      if (refreshToken) _store.set("campus_refresh_token", refreshToken);
      else _store.delete("campus_refresh_token");
    },

    clearTokens() {
      _store.delete("campus_access_token");
      _store.delete("campus_refresh_token");
    },

    lastRequest() {
      return requests[requests.length - 1];
    },

    findRequests(method, urlPart) {
      return requests.filter(
        (r) => r.method === method && r.url.includes(urlPart),
      );
    },
  };

  return api;
}
