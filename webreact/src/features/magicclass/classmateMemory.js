/**
 * 同学记忆与预算的本地模型。
 *
 * 只保存**同学自己说过的话**与页标题，不含学生原话；超出上限时丢最旧的，
 * 与上游契约一致。坏存档只丢坏字段。
 */

export const CLASSMATE_BUDGET = 240_000;
export const MAX_MEMORY_PAGES = 8;
export const MAX_PAGE_CHARS = 200;
export const MAX_MEMORY_LINES = 12;
export const MAX_LINE_CHARS = 400;
export const MAX_RECENT = 7;

export function emptyClassmateMemory() {
  return { pages: [], lines: [], recentAgentIds: [], usage: 0 };
}

function textOf(value, limit) {
  return typeof value === "string" && value ? value.slice(0, limit) : "";
}

export function normalizeMemory(raw) {
  if (!raw || typeof raw !== "object") return emptyClassmateMemory();
  const pages = (Array.isArray(raw.pages) ? raw.pages : [])
    .map((page) => textOf(page, MAX_PAGE_CHARS))
    .filter(Boolean)
    .slice(-MAX_MEMORY_PAGES);
  const lines = (Array.isArray(raw.lines) ? raw.lines : [])
    .filter((line) => line && typeof line.agentId === "string" && line.agentId.trim() && textOf(line.text, MAX_LINE_CHARS).trim())
    .map((line) => ({ agentId: line.agentId, text: textOf(line.text, MAX_LINE_CHARS) }))
    .slice(-MAX_MEMORY_LINES);
  const recentAgentIds = (Array.isArray(raw.recentAgentIds) ? raw.recentAgentIds : [])
    .filter((id) => typeof id === "string" && id)
    .slice(-MAX_RECENT);
  const usage = Number(raw.usage);
  return {
    pages,
    lines,
    recentAgentIds,
    usage: Number.isFinite(usage) && usage > 0 ? Math.floor(usage) : 0,
  };
}

export function memoryKey(stageId) {
  return stageId ? `campusmate:classroom-classmates:v1:${stageId}` : "";
}

export function readMemory(storage, key) {
  if (!key || !storage) return emptyClassmateMemory();
  try {
    const raw = storage.getItem(key);
    return raw ? normalizeMemory(JSON.parse(raw)) : emptyClassmateMemory();
  } catch {
    return emptyClassmateMemory();
  }
}

export function writeMemory(storage, key, state) {
  if (!key || !storage) return false;
  try {
    storage.setItem(key, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}

export function addPage(state, title) {
  const page = textOf(title, MAX_PAGE_CHARS);
  if (!page) return state;
  const pages = [...state.pages.filter((item) => item !== page), page].slice(-MAX_MEMORY_PAGES);
  return { ...state, pages };
}

export function addLines(state, messages = []) {
  const incoming = messages
    .filter((message) => message && typeof message.agentId === "string" && message.agentId.trim() && textOf(message.text, MAX_LINE_CHARS).trim())
    .map((message) => ({ agentId: message.agentId, text: textOf(message.text, MAX_LINE_CHARS).trim() }));
  if (!incoming.length) return state;
  return {
    ...state,
    lines: [...state.lines, ...incoming].slice(-MAX_MEMORY_LINES),
    recentAgentIds: [...state.recentAgentIds, ...incoming.map((message) => message.agentId)].slice(-MAX_RECENT),
  };
}

export function bumpUsage(state, tokens) {
  const add = Number(tokens);
  if (!Number.isFinite(add) || add <= 0) return state;
  return { ...state, usage: state.usage + Math.floor(add) };
}

export function budgetLeft(state, budget = CLASSMATE_BUDGET) {
  return Math.max(0, budget - (state?.usage || 0));
}

export function memoryPayload(state) {
  return {
    pages: state.pages,
    lines: state.lines,
    recentAgentIds: state.recentAgentIds,
  };
}
