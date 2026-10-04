import axios from "axios";
import { clearStoredSession } from "../../app/auth.js";
import { normalizeApiError } from "../contracts.js";

const viteEnv = import.meta.env || {};
export const BASE_URL = viteEnv.VITE_API_BASE_URL || "/api/v1";

function storageOrDefault(storage) {
  return storage || globalThis.localStorage;
}

export function createClient(baseUrl = BASE_URL, storage = globalThis.localStorage) {
  const client = axios.create({ baseURL: baseUrl, timeout: 8000, withCredentials: true });
  const authStorage = () => storageOrDefault(storage);
  const readTokenPair = () => {
    const activeStorage = authStorage();
    return {
      access: activeStorage?.getItem("campus_access_token") || null,
      refresh: activeStorage?.getItem("campus_refresh_token") || null,
    };
  };
  const pairKey = (pair) => JSON.stringify([pair?.access || null, pair?.refresh || null]);
  const refreshLineage = new Map();
  let knownPairKey = pairKey(readTokenPair());
  const observeCurrentPair = () => {
    const pair = readTokenPair();
    const key = pairKey(pair);
    // A token-pair change outside a refresh recorded by this client means a
    // new login/logout owns storage; old requests must not cross that boundary.
    if (key !== knownPairKey) {
      refreshLineage.clear();
      knownPairKey = key;
    }
    return { pair, key };
  };
  const isRefreshSuccessor = (sentPair, currentKey) => {
    const start = pairKey(sentPair);
    if (start === currentKey) return true;
    const visited = new Set([start]);
    let key = start;
    while (refreshLineage.has(key)) {
      key = refreshLineage.get(key);
      if (key === currentKey) return true;
      if (visited.has(key)) return false;
      visited.add(key);
    }
    return false;
  };
  const currentAuthorization = () => {
    const token = authStorage()?.getItem("campus_access_token");
    return token ? `Bearer ${token}` : undefined;
  };

  const refreshOnce = async () => {
    const activeStorage = authStorage();
    const beforePair = readTokenPair();
    const refreshToken = activeStorage?.getItem("campus_refresh_token");
    if (!refreshRequest || refreshRequest.token !== refreshToken) {
      refreshRequest = {
        token: refreshToken,
        promise: refreshAccessToken(baseUrl, activeStorage),
      };
    }
    const pendingRefresh = refreshRequest;
    try {
      const token = await pendingRefresh.promise;
      const afterPair = readTokenPair();
      if (beforePair.access && beforePair.refresh && afterPair.access === token && afterPair.refresh) {
        const beforeKey = pairKey(beforePair);
        const afterKey = pairKey(afterPair);
        if (beforeKey !== afterKey) {
          refreshLineage.set(beforeKey, afterKey);
          if (refreshLineage.size > 16) refreshLineage.delete(refreshLineage.keys().next().value);
        }
        knownPairKey = afterKey;
      }
      return token;
    } finally {
      if (refreshRequest === pendingRefresh) refreshRequest = null;
    }
  };

  client.authorizedFetch = async (input, init = {}) => {
    const headers = new Headers(init.headers || {});
    const sentPair = readTokenPair();
    const sentAuthorization = sentPair.access ? `Bearer ${sentPair.access}` : undefined;
    if (sentAuthorization) headers.set("Authorization", sentAuthorization);
    const requestInit = { ...init, headers };
    const response = await fetch(input, requestInit);
    if (response.status !== 401 || !sentAuthorization || init.signal?.aborted) return response;

    const current = observeCurrentPair();
    if (current.key !== pairKey(sentPair)) {
      if (!isRefreshSuccessor(sentPair, current.key)) return response;
      headers.set("Authorization", currentAuthorization());
      return fetch(input, requestInit);
    }

    const token = await refreshOnce();
    if (init.signal?.aborted) {
      throw new DOMException("The operation was aborted", "AbortError");
    }
    const refreshedAuthorization = currentAuthorization();
    if (!refreshedAuthorization || refreshedAuthorization !== `Bearer ${token}`) return response;
    headers.set("Authorization", refreshedAuthorization);
    return fetch(input, requestInit);
  };
  client.interceptors.request.use((config) => {
    const observed = observeCurrentPair();
    if (config._retried && (!config._retryAuthTokenPair
      || pairKey(config._retryAuthTokenPair) !== observed.key)) {
      throw new Error("登录状态已变更，请重试");
    }
    config._authTokenPair = observed.pair;
    const token = observed.pair.access;
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  });

  let refreshRequest = null;
  client.interceptors.response.use((response) => response, async (error) => {
    const original = error.config;
    const url = original?.url || "";
    // 5xx 只写开发诊断日志，不向用户展示原始英文（UI 使用 userErrorMessage 取中文文案）
    if (error.response?.status >= 500) {
      console.warn("[api] 5xx", url, error.response.status, error.message);
    }
    const detail = error.response?.data?.detail;
    const chaoxingAuthError = url.includes("/chaoxing/") && (
      detail === "reauth_required" || detail === "Chaoxing credentials not found"
      || (typeof detail === "string" && detail.startsWith("Chaoxing login failed:"))
    );
    if (error.response?.status !== 401 || !original || original._retried || chaoxingAuthError
      || url.includes("/auth/login") || url.includes("/auth/refresh")) return Promise.reject(error);

    const authStorage = storageOrDefault(storage);
    const sentAuthorization = original.headers?.get?.("Authorization") ?? original.headers?.Authorization;
    const current = observeCurrentPair();
    const sentPair = original._authTokenPair;
    // A late 401 may use the latest access token only when it is a recorded
    // successor produced by this client's successful refresh.
    if (sentAuthorization !== (current.pair.access ? `Bearer ${current.pair.access}` : undefined)) {
      if (!sentPair || !isRefreshSuccessor(sentPair, current.key)) {
        return Promise.reject(error);
      }
      original._retried = true;
      original._retryAuthTokenPair = current.pair;
      original.headers.Authorization = `Bearer ${current.pair.access}`;
      return client(original);
    }
    if (!sentPair || pairKey(sentPair) !== current.key) {
      return Promise.reject(error);
    }

    original._retried = true;
    try {
      const token = await refreshOnce();
      if (authStorage.getItem("campus_access_token") !== token) {
        return Promise.reject(error);
      }
      original._retryAuthTokenPair = readTokenPair();
      original.headers.Authorization = `Bearer ${token}`;
      return client(original);
    } catch (refreshError) {
      return Promise.reject(refreshError);
    }
  });
  // Normalize diagnostics after authentication; generic user-facing defaults
  // remain in userErrorMessage so each page can supply its own context.
  client.interceptors.response.use((response) => response, (error) => Promise.reject(normalizeApiError(error)));
  return client;
}

async function refreshAccessToken(baseUrl, storage) {
  const refreshToken = storage.getItem("campus_refresh_token");
  if (!refreshToken) {
    clearStoredSession(storage);
    redirectToLogin();
    throw new Error("登录已过期，请重新登录");
  }
  let data;
  try {
    ({ data } = await axios.post(`${baseUrl}/auth/refresh`, { refresh_token: refreshToken }, { timeout: 8000 }));
  } catch (error) {
    // A later logout or login owns storage now; this request must not erase it.
    if (storage.getItem("campus_refresh_token") !== refreshToken) {
      throw new Error("登录状态已变更，请重试");
    }
    if ([401, 403].includes(error.response?.status)) {
      clearStoredSession(storage);
      redirectToLogin();
      throw new Error("登录已过期，请重新登录");
    }
    throw new Error("登录状态暂时无法刷新，请稍后重试", { cause: error });
  }
  // The same guard also prevents a late successful refresh from restoring a
  // logged-out session or replacing the tokens of a different account.
  if (storage.getItem("campus_refresh_token") !== refreshToken) {
    throw new Error("登录状态已变更，请重试");
  }
  saveTokenPair(data, storage);
  return data.access_token;
}

export { refreshAccessToken };

function redirectToLogin() {
  if (typeof location !== "undefined" && location.pathname !== "/login") location.href = "/login";
}

const client = createClient();
export { client };

export function saveTokenPair(data, storage = globalThis.localStorage) {
  storage.setItem("campus_access_token", data.access_token);
  storage.setItem("campus_refresh_token", data.refresh_token);
}

export const applyTokenPair = saveTokenPair;
