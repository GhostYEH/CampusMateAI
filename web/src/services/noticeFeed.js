export function normalizeNoticeItems(response) {
  const items = Array.isArray(response) ? response : response?.items || [];
  return items.map((item) => ({
    ...item,
    has_read: !item.unread,
    published_at: item.time || item.published_at || null,
  }));
}

export function shouldMarkAnnouncementRead(item) {
  return item?.kind === "announcement" && !item.has_read;
}

export function safeNoticeSourceUrl(item) {
  if (item?.kind !== "unified" || !item.source_url) return null;
  try {
    const url = new URL(item.source_url, window.location.href);
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

export function noticeMatchesFilters(item, filters) {
  const matchesSource = filters.source === "all" || item.source === filters.source;
  const matchesRead = filters.readFilter === "all" || !item.has_read;
  const keyword = `${item.title || ""} ${item.content || ""}`.toLocaleLowerCase();
  return matchesSource && matchesRead && keyword.includes((filters.query || "").trim().toLocaleLowerCase());
}
