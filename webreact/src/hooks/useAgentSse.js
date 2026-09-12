/**
 * useAgentSse — 订阅 agent run 事件流。
 *
 * 使用 authenticated fetch + ReadableStream（agentSseStream），不用 EventSource。
 * - 从 localStorage 读 token（与 api.js 一致）。
 * - 401 时调 refreshAccessToken 刷新。
 * - 按 sequence 去重并累积事件。
 * - 暴露连接状态供 UI 显示 connecting/open/reconnecting/closed/error/unauthorized。
 * - 组件卸载或 enabled=false 时主动取消。
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createAgentSseStream } from "../data/agentSseStream.js";
import { agentRunStreamUrl } from "../data/agentRuntimeApi.js";
import { BASE_URL, refreshAccessToken } from "../data/api.js";
import { mergeEvents, lastEventSequence, SSE_RECONNECT_MAX_MS } from "../data/agentContracts.js";

const STATUS_LABEL = {
  idle: "等待开始",
  connecting: "正在连接…",
  open: "已连接",
  reconnecting: "正在重连…",
  closed: "已关闭",
  error: "连接异常",
  unauthorized: "登录已过期",
};

export function useAgentSse({ runId, onEvent, enabled = true, maxReconnects = 6 }) {
  const [status, setStatus] = useState("idle");
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(null);
  const streamRef = useRef(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const buildHeaders = useCallback(() => {
    const token = globalThis.localStorage?.getItem("campus_access_token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);

  const refreshAuth = useCallback(async () => {
    await refreshAccessToken(BASE_URL, globalThis.localStorage);
  }, []);

  useEffect(() => {
    if (!enabled || !runId) {
      setStatus("idle");
      return;
    }
    let cancelled = false;
    setStatus("connecting");
    setError(null);

    const stream = createAgentSseStream({
      url: `${BASE_URL}${agentRunStreamUrl(runId)}`,
      buildHeaders,
      refreshAuth,
      maxReconnects,
      onEvent: (evt) => {
        if (cancelled) return;
        setEvents((prev) => mergeEvents(prev, [evt.payload], lastEventSequence(prev)));
        try { onEventRef.current?.(evt.payload); } catch { /* 回调错误不影响流 */ }
      },
      onStatus: (s, info) => {
        if (cancelled) return;
        if (s === "error") setError(info?.message || "连接异常");
        if (s === "unauthorized") setError(info?.message || "登录已过期");
        setStatus(s);
      },
    });
    streamRef.current = stream;

    return () => {
      cancelled = true;
      stream.cancel();
      streamRef.current = null;
    };
  }, [runId, enabled, buildHeaders, refreshAuth, maxReconnects]);

  const cancel = useCallback(() => {
    streamRef.current?.cancel();
  }, []);

  const lastEventId = useMemo(() => {
    const last = events[events.length - 1];
    return last?.id || null;
  }, [events]);

  return {
    status,
    statusLabel: STATUS_LABEL[status] || "状态待确认",
    events,
    lastEventId,
    error,
    cancel,
    isLive: status === "open" || status === "connecting" || status === "reconnecting",
  };
}

export { STATUS_LABEL as AGENT_SSE_STATUS_LABEL, SSE_RECONNECT_MAX_MS };