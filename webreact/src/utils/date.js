export function toDate(value) {
  if (value == null || value === "") return null;
  const numeric = typeof value === "number" ? value : typeof value === "string" && /^\d+(?:\.\d+)?$/.test(value.trim()) ? Number(value) : null;
  const timestamp = numeric == null ? value : Math.abs(numeric) < 10_000_000_000 ? numeric * 1000 : numeric;
  const date = new Date(timestamp);
  return Number.isNaN(date.valueOf()) ? null : date;
}

export function formatDateTime(value, options, fallback) {
  const date = toDate(value);
  return date ? new Intl.DateTimeFormat("zh-CN", options).format(date) : fallback;
}

export function localDateKey(value = new Date()) {
  const date = value instanceof Date ? value : toDate(value);
  if (!date) return "";
  return [date.getFullYear(), date.getMonth() + 1, date.getDate()]
    .map((part, index) => index === 0 ? String(part) : String(part).padStart(2, "0"))
    .join("-");
}

export function isSameLocalDate(left, right = new Date()) {
  return localDateKey(left) !== "" && localDateKey(left) === localDateKey(right);
}

export function formatTimestamp(value) {
  if (!value) return "—";
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return d.toLocaleString("zh-CN", { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return String(value);
  }
}

export function formatRelativeTime(iso) {
  if (!iso) return "未知";
  try {
    const d = new Date(iso);
    const now = Date.now();
    const diff = now - d.getTime();
    if (diff < 60000) return "刚刚";
    if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
    return d.toLocaleDateString("zh-CN");
  } catch { return "未知"; }
}
