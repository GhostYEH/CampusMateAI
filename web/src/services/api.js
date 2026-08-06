import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";
const client = axios.create({ baseURL: BASE_URL, timeout: 8000 });
client.interceptors.request.use((config) => {
  const token = localStorage.getItem("campus_access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ===== access token 过期后自动用 refresh token 换发并重试 =====
// access token 有效期仅 30 分钟;遇到 401 时用 localStorage 中的 refresh token
// 调用 /auth/refresh 换取新 token,然后重放原请求。refresh token 失效则回到登录页。
let _refreshingPromise = null;

function _clearSessionAndRedirect() {
  localStorage.removeItem("campus_access_token");
  localStorage.removeItem("campus_refresh_token");
  localStorage.removeItem("campus_session");
  if (location.pathname !== "/login") location.href = "/login";
}

async function _refreshAccessToken() {
  const refreshToken = localStorage.getItem("campus_refresh_token");
  if (!refreshToken) {
    _clearSessionAndRedirect();
    throw new Error("登录已过期，请重新登录");
  }
  try {
    // 用独立的 axios 调用，避免再走上面的请求拦截器附加已过期的 access token
    const { data } = await axios.post(`${BASE_URL}/auth/refresh`, { refresh_token: refreshToken });
    localStorage.setItem("campus_access_token", data.access_token);
    localStorage.setItem("campus_refresh_token", data.refresh_token);
    return data.access_token;
  } catch (e) {
    _clearSessionAndRedirect();
    throw new Error("登录已过期，请重新登录");
  }
}

client.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const original = error.config;
    // 仅对 401 且未重试过、且不是登录/刷新接口本身的请求做刷新重试
    if (
      error.response?.status === 401 &&
      original &&
      !original._retried &&
      !original.url?.includes("/auth/login") &&
      !original.url?.includes("/auth/refresh")
    ) {
      original._retried = true;
      try {
        // 多个请求同时 401 时，共享同一次刷新，避免并发重复刷新导致 refresh token 被撤销
        if (!_refreshingPromise) _refreshingPromise = _refreshAccessToken();
        const newToken = await _refreshingPromise;
        _refreshingPromise = null;
        original.headers.Authorization = `Bearer ${newToken}`;
        return client(original);
      } catch (e) {
        _refreshingPromise = null;
        return Promise.reject(e);
      }
    }
    return Promise.reject(error);
  }
);

export async function probeBackend() { try { await client.get("/health"); return true; } catch { return false; } }

export async function realLogin(username, password) {
  const { data } = await client.post("/auth/login", { username, password });
  localStorage.setItem("campus_access_token", data.access_token);
  localStorage.setItem("campus_refresh_token", data.refresh_token);
  const me = await client.get("/auth/me");
  return me.data.user || me.data;
}

/** 非流式聊天（向后兼容） */
export async function chat(message) {
  const { data } = await client.post("/counselor/chat", { message, session_id: "web-session" });
  return data;
}

/**
 * 流式聊天 — 使用 fetch POST + SSE 逐事件回调。
 *
 * @param {string} message          用户消息
 * @param {object} callbacks
 * @param {(sources: Array) => void}   callbacks.onSources  - sources 事件
 * @param {(text: string, mode: string) => void} callbacks.onChunk   - chunk 事件
 * @param {(meta: object) => void}    callbacks.onDone     - done 事件
 * @param {(err: Error) => void}      callbacks.onError    - 错误/异常
 * @param {AbortSignal}               [callbacks.signal]   - 可取消信号
 */
export async function chatStream(message, { onSources, onChunk, onDone, onError, signal } = {}) {
  const token = localStorage.getItem("campus_access_token");
  try {
    const resp = await fetch(`${BASE_URL}/counselor/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ message, stream: true }),
      signal,
    });

    if (!resp.ok) {
      const body = await resp.text().catch(() => "");
      onError?.(new Error(`服务器错误 (${resp.status}): ${body.slice(0, 120)}`));
      return;
    }

    const reader = resp.body?.getReader();
    if (!reader) {
      onError?.(new Error("浏览器不支持流式读取"));
      return;
    }

    const decoder = new TextDecoder();
    let buffer = "";
    let currentEvent = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE 事件以 \n\n 分隔
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || ""; // 最后一段可能不完整，留在 buffer

      for (const block of parts) {
        if (!block.trim()) continue;
        const lines = block.split("\n");
        let eventType = currentEvent;
        let dataStr = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            dataStr = line.slice(6);
          }
        }
        if (!dataStr) continue;
        try {
          const data = JSON.parse(dataStr);
          if (eventType === "sources") onSources?.(data.sources || []);
          else if (eventType === "chunk") onChunk?.(data.text || "", data.mode || "llm");
          else if (eventType === "done") onDone?.(data);
          else if (eventType === "error") onError?.(new Error(data.message || "未知错误"));
        } catch {
          // 跳过解析失败的 chunk
        }
        currentEvent = "";
      }
    }
    // 处理 buffer 中残余数据
    if (buffer.trim()) {
      const lines = buffer.trim().split("\n");
      let eventType = "";
      let dataStr = "";
      for (const line of lines) {
        if (line.startsWith("event: ")) eventType = line.slice(7).trim();
        else if (line.startsWith("data: ")) dataStr = line.slice(6);
      }
      if (dataStr) {
        try {
          const data = JSON.parse(dataStr);
          if (eventType === "done") onDone?.(data);
        } catch { /* ignore */ }
      }
    }
  } catch (err) {
    if (err.name === "AbortError") return;
    onError?.(err);
  }
}

export async function extractNotice(text) {
  const { data } = await client.post("/notices/extract-multi", { text });
  return data;
}

export default client;
