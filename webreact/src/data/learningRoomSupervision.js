/**
 * 浏览器端课堂监督只使用页面可见性与交互间隔，不采集摄像头、麦克风或人脸。
 * 这些函数保持纯函数，便于测试和在其他 WebView 客户端复用。
 */
export const ATTENTION_LABELS = {
  FOCUSED: "专注听课",
  POSSIBLY_DISTRACTED: "可能分心",
  DISTRACTED: "明显分心",
  AWAY: "暂时离开",
  UNKNOWN: "状态未知",
};

export const HIDDEN_AWAY_AFTER_MS = 60_000;
export const IDLE_DISTRACTED_AFTER_MS = 180_000;
export const ACTIVE_WINDOW_MS = 90_000;

export function attentionLabel(state) {
  return ATTENTION_LABELS[state] || ATTENTION_LABELS.UNKNOWN;
}

/**
 * 页面可见且最近有交互 => 专注；短时切走/长时间无操作 => 可能分心；
 * 页面隐藏超过 1 分钟 => 暂时离开。浏览器标签被节流时，调用方应在
 * visibilitychange 事件里立即补报一次，避免状态停在旧值。
 */
export function attentionSignal({ hidden, hiddenForMs = 0, idleForMs = 0 }) {
  if (hidden) return hiddenForMs >= HIDDEN_AWAY_AFTER_MS ? "AWAY" : "POSSIBLY_DISTRACTED";
  if (idleForMs >= IDLE_DISTRACTED_AFTER_MS) return "POSSIBLY_DISTRACTED";
  return idleForMs <= ACTIVE_WINDOW_MS ? "FOCUSED" : "UNKNOWN";
}

/**
 * 只挑出“发给我的或全班的”提醒，并排除自己发出的提醒；第一次拉取只记录游标，不把历史提醒当成新消息。
 */
export function pickFreshNudge({ nudges = [], after = 0, meUid, initialized = false, extraIds = [] }) {
  const ids = [...nudges.map((item) => item.id), ...extraIds].filter((id) => Number.isFinite(id));
  const newest = ids.length ? Math.max(...ids) : after;
  if (!initialized) return { newest, nudge: null };
  return {
    newest,
    nudge: nudges.find((item) => item.id > after &&
      (item.target_uid == null || item.target_uid === meUid) &&
      item.from_uid !== meUid) || null,
  };
}

export function mergeSupervisionNudge(current, incoming) {
  if (!incoming) return current;
  if (current && current.id >= incoming.id) return current;
  return incoming;
}
