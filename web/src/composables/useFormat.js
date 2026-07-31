export function formatDateTime(value, options = {}) {
  if (!value) return options.fallback || "未设置";
  try {
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) return options.fallback || "未设置";
    return new Intl.DateTimeFormat("zh-CN", {
      year: options.year || "numeric",
      month: options.month || "numeric",
      day: options.day || "numeric",
      hour: options.hour || "2-digit",
      minute: options.minute || "2-digit",
    }).format(dt);
  } catch {
    return options.fallback || "未设置";
  }
}

export function formatDate(value, fallback = "未设置") {
  return formatDateTime(value, { hour: undefined, minute: undefined, fallback });
}

export function formatRelativeTime(value) {
  if (!value) return "未知";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return "未知";
  const diff = Date.now() - dt.getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} 天前`;
  return formatDate(value);
}

export function formatFileSize(bytes) {
  if (!bytes && bytes !== 0) return "未知大小";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

export function toLocalDatetimeInput(iso) {
  if (!iso) return "";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}`;
}

export function fromLocalDatetimeInput(local) {
  if (!local) return null;
  const dt = new Date(local);
  if (Number.isNaN(dt.getTime())) return null;
  return dt.toISOString();
}

export function isOverdue(deadline) {
  if (!deadline) return false;
  return new Date(deadline).getTime() < Date.now();
}

export function daysUntil(deadline) {
  if (!deadline) return null;
  const diff = new Date(deadline).getTime() - Date.now();
  return Math.ceil(diff / 86400000);
}

export function downloadCsv(filename, rows) {
  if (!rows || !rows.length) return;
  const headers = Object.keys(rows[0]);
  const escape = (v) => {
    if (v === null || v === undefined) return "";
    const s = String(v);
    if (s.includes(",") || s.includes('"') || s.includes("\n")) {
      return `"${s.replace(/"/g, '""')}"`;
    }
    return s;
  };
  const lines = [
    headers.join(","),
    ...rows.map((row) => headers.map((h) => escape(row[h])).join(",")),
  ];
  const blob = new Blob(["\uFEFF" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function copyToClipboard(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(text);
  }
  return new Promise((resolve, reject) => {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      resolve();
    } catch (err) {
      reject(err);
    }
  });
}