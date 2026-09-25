import axios from "axios";
import { clearStoredSession } from "../../app/auth.js";

const viteEnv = import.meta.env || {};
export const BASE_URL = viteEnv.VITE_API_BASE_URL || "/api/v1";

function storageOrDefault(storage) {
  return storage || globalThis.localStorage;
}

export function createClient(baseUrl = BASE_URL, storage = globalThis.localStorage) {
  const client = axios.create({ baseURL: baseUrl, timeout: 8000, withCredentials: true });
  client.interceptors.request.use((config) => {
    const token = storageOrDefault(storage)?.getItem("campus_access_token");
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
    const currentAccessToken = authStorage?.getItem("campus_access_token");
    // A response from an earlier session must never be replayed as the new user.
    if (sentAuthorization !== (currentAccessToken ? `Bearer ${currentAccessToken}` : undefined)) {
      return Promise.reject(error);
    }

    original._retried = true;
    const refreshToken = authStorage?.getItem("campus_refresh_token");
    if (!refreshRequest || refreshRequest.token !== refreshToken) {
      refreshRequest = {
        token: refreshToken,
        promise: refreshAccessToken(baseUrl, authStorage),
      };
    }
    const pendingRefresh = refreshRequest;
    try {
      const token = await pendingRefresh.promise;
      if (authStorage.getItem("campus_access_token") !== token) {
        return Promise.reject(error);
      }
      original.headers.Authorization = `Bearer ${token}`;
      return client(original);
    } catch (refreshError) {
      return Promise.reject(refreshError);
    } finally {
      if (refreshRequest === pendingRefresh) refreshRequest = null;
    }
  });
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
    ({ data } = await axios.post(`${baseUrl}/auth/refresh`, { refresh_token: refreshToken }));
  } catch {
    // A later logout or login owns storage now; this request must not erase it.
    if (storage.getItem("campus_refresh_token") !== refreshToken) {
      throw new Error("登录状态已变更，请重试");
    }
    clearStoredSession(storage);
    redirectToLogin();
    throw new Error("登录已过期，请重新登录");
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
