/**
 * Agent Runtime SSE 客户端。
 *
 * 关键约束（任务 §1）：
 * - 浏览器原生 EventSource 不能附加 Authorization，禁止 token query。
 *   因此使用 authenticated fetch + ReadableStream 实现 SSE parser。
 * - 发送 Last-Event-ID 续传。
 * - 按 sequence 去重。
 * - 处理 CRLF、分块 JSON、多行 data。
 * - 401 时刷新 token 后重连。
 * - 退避重连。
 * - 主动取消。
 *
 * 本模块不导入 React，fetch 与 refreshAuth 注入，便于 node:test。
 */
import { reconnectDelay as defaultReconnectDelay, lastEventSequence } from "./agentContracts.js";

/**
 * 把累积 buffer 拆成完整 SSE 帧和剩余片段。
 * 帧以空行分隔（支持 \n\n 与 \r\n\r\n）。
 * 返回 { frames: string[], remainder: string }。
 */
export function splitSseBlocks(buffer) {
  if (!buffer) return { blocks: [], remainder: "" };
  const re = /\r?\n\r?\n/;
  const blocks = [];
  let rest = buffer;
  let match;
  while ((match = re.exec(rest)) !== null) {
    blocks.push(rest.slice(0, match.index));
    rest = rest.slice(match.index + match[0].length);
  }
  return { blocks, remainder: rest };
}

/**
 * 解析单个 SSE 帧文本为 { id, event, data }。
 * - `id: xxx` → id（Last-Event-ID）
 * - `event: xxx` → event 类型
 * - `data: xxx`（多行）→ 用 \n 连接
 * - `: xxx` → 注释，忽略
 * 无 data 时返回 null。
 */
export function decodeSseFrame(frameText) {
  if (!frameText) return null;
  let id = null;
  let event = null;
  const dataLines = [];
  const lines = frameText.split(/\r?\n/);
  for (const line of lines) {
    if (!line) continue;
    if (line.startsWith(":")) continue;
    const colon = line.indexOf(":");
    if (colon === -1) continue;
    const field = line.slice(0, colon);
    const value = line.slice(colon + 1).replace(/^ /, "");
    if (field === "id") id = value;
    else if (field === "event") event = value;
    else if (field === "data") dataLines.push(value);
  }
  if (dataLines.length === 0 && id === null && event === null) return null;
  return { id, event, data: dataLines.join("\n") };
}

/**
 * 解析 data 文本为 JSON payload。失败返回 null（分块未完成时不报错）。
 */
export function decodeSsePayload(dataText) {
  if (!dataText) return null;
  try {
    return JSON.parse(dataText);
  } catch {
    return null;
  }
}

/**
 * 从一整段 buffer 提取所有完整事件 payload。
 * 返回 { events: [{id, event, payload}], remainder, lastEventId }。
 * lastEventId 为本批次中最后一个带 id 帧的 id（用于续传）。
 */
export function parseSseChunk(buffer, knownLastEventId = null) {
  const { blocks, remainder } = splitSseBlocks(buffer);
  const events = [];
  let lastEventId = knownLastEventId;
  for (const block of blocks) {
    const frame = decodeSseFrame(block);
    if (!frame) continue;
    const payload = decodeSsePayload(frame.data);
    if (frame.id) lastEventId = frame.id;
    events.push({ id: frame.id, event: frame.event, payload });
  }
  return { events, remainder, lastEventId };
}

/**
 * 创建受控 SSE 流。返回控制器 { cancel, getLastEventId, getMaxSequence }。
 *
 * options:
 * - url: string
 * - buildHeaders: () => object  （含 Authorization 等；每次连接重新构建以刷新 token）
 * - onEvent: (event) => void    （event = { id, event, payload }）
 * - onStatus: (status, info) => void  status ∈ connecting|open|reconnecting|closed|error|unauthorized
 * - signal: AbortSignal         （外部取消）
 * - lastEventId: string|null    （初始续传游标）
 * - fetchImpl: typeof fetch     （注入测试；默认 globalThis.fetch）
 * - refreshAuth: async () => void （401 时刷新 token；失败抛错则停止）
 * - delayFn: (attempt) => ms
 * - maxReconnects: number       （默认 6；超过后 status=error 并停止）
 */
export function createAgentSseStream({
  url,
  buildHeaders,
  onEvent,
  onStatus,
  signal,
  lastEventId = null,
  fetchImpl,
  refreshAuth,
  delayFn = defaultReconnectDelay,
  maxReconnects = 6,
}) {
  const fetch_ = fetchImpl || globalThis.fetch;
  if (typeof fetch_ !== "function") {
    throw new Error("当前环境不支持 fetch，无法建立 SSE 连接");
  }

  let cancelled = false;
  let currentAbort = null;
  let lastEvent = lastEventId;
  let maxSequence = 0;
  let attempt = 0;
  const seenSequences = new Set();

  function emit(status, info) {
    try { onStatus?.(status, info); } catch { /* 状态回调不应中断流 */ }
  }

  function dispatch(event) {
    if (!event || !event.payload) return;
    const seq = event.payload?.sequence;
    if (typeof seq === "number") {
      if (seq <= maxSequence || seenSequences.has(seq)) return;
      seenSequences.add(seq);
      if (seq > maxSequence) maxSequence = seq;
    }
    if (event.id) lastEvent = event.id;
    try { onEvent?.(event); } catch { /* 单事件回调错误不中断流 */ }
  }

  async function refreshAndContinue() {
    if (!refreshAuth) {
      emit("unauthorized", { message: "登录已过期" });
      return false;
    }
    try {
      await refreshAuth();
      return true;
    } catch {
      emit("unauthorized", { message: "登录已过期，请重新登录" });
      return false;
    }
  }

  async function connect() {
    while (!cancelled) {
      if (signal?.aborted) { cancelled = true; break; }
      currentAbort = new AbortController();
      const externalAbort = () => { cancelled = true; currentAbort?.abort(); };
      signal?.addEventListener("abort", externalAbort, { once: true });

      emit(attempt === 0 ? "connecting" : "reconnecting", { attempt });

      let response;
      try {
        const headers = { Accept: "text/event-stream", ...(buildHeaders?.() || {}) };
        if (lastEvent) headers["Last-Event-ID"] = lastEvent;
        response = await fetch_(url, {
          method: "GET",
          headers,
          signal: currentAbort.signal,
        });
      } catch (err) {
        signal?.removeEventListener("abort", externalAbort);
        if (cancelled || err?.name === "AbortError") break;
        if (attempt >= maxReconnects) { emit("error", { message: "连接失败，已停止重连" }); break; }
        emit("reconnecting", { attempt: attempt + 1, reason: "network" });
        await sleep(delayFn(attempt));
        attempt += 1;
        continue;
      }

      if (response.status === 401) {
        signal?.removeEventListener("abort", externalAbort);
        const ok = await refreshAndContinue();
        if (!ok) break;
        attempt += 1;
        continue;
      }

      if (response.status === 409) {
        // 游标失效(不属于该 Run / 已不存在):丢弃游标重连,由服务端从头推流,
        // 并结合 REST 事件列表做一次安全全量归并,绝不静默丢事件。
        signal?.removeEventListener("abort", externalAbort);
        lastEvent = null;
        seenSequences.clear();
        maxSequence = 0;
        if (attempt >= maxReconnects) { emit("error", { message: "事件游标失效" }); break; }
        emit("reconnecting", { attempt: attempt + 1, reason: "cursor" });
        await sleep(delayFn(attempt));
        attempt += 1;
        continue;
      }

      if (!response.ok || !response.body) {
        signal?.removeEventListener("abort", externalAbort);
        if (attempt >= maxReconnects) { emit("error", { message: `服务返回 ${response.status}` }); break; }
        emit("reconnecting", { attempt: attempt + 1, reason: "status", status: response.status });
        await sleep(delayFn(attempt));
        attempt += 1;
        continue;
      }


      emit("open", {});

      let pumpOk = false;
      try {
        await pumpStream(response.body);
        pumpOk = true;
      } catch (err) {
        if (cancelled || err?.name === "AbortError") break;
      } finally {
        signal?.removeEventListener("abort", externalAbort);
      }

      if (cancelled) break;
      if (signal?.aborted) { cancelled = true; break; }
      if (!pumpOk) { attempt += 1; continue; }
      if (attempt >= maxReconnects) { emit("error", { message: "连接已断开，已停止重连" }); break; }
      emit("reconnecting", { attempt: attempt + 1, reason: "eof" });
      await sleep(delayFn(attempt));
      attempt += 1;
    }
    if (!signal?.aborted && !cancelled) emit("closed", {});
    else emit("closed", { reason: "cancelled" });
  }

  async function pumpStream(body) {
    const reader = body.getReader?.();
    if (!reader) throw new Error("当前浏览器不支持流式读取");
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parsed = parseSseChunk(buffer, lastEvent);
      buffer = parsed.remainder;
      for (const evt of parsed.events) dispatch(evt);
    }
    if (buffer.trim()) {
      const parsed = parseSseChunk(buffer + "\n\n", lastEvent);
      for (const evt of parsed.events) dispatch(evt);
    }
  }

  function sleep(ms) {
    return new Promise((resolve) => {
      const t = setTimeout(resolve, ms);
      if (currentAbort) {
        currentAbort.signal.addEventListener("abort", () => { clearTimeout(t); resolve(); }, { once: true });
      }
    });
  }

  const promise = connect();

  return {
    cancel() {
      cancelled = true;
      currentAbort?.abort();
    },
    done: promise,
    getLastEventId() { return lastEvent; },
    getMaxSequence() { return maxSequence; },
  };
}