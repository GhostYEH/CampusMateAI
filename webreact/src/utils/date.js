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
