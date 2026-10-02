const LEGACY_KEY = "campus_counselor_sessions";

export function counselorSessionsKey(identity) {
  return identity && identity !== "anon" ? `${LEGACY_KEY}:${encodeURIComponent(identity)}` : null;
}

export function readCounselorSessions(identity, storage = globalThis.localStorage) {
  try {
    // Ignore unowned legacy records instead of assigning them to the next
    // login. Preserve the original storage so history is not silently deleted.
    const key = counselorSessionsKey(identity);
    if (!key) return [];
    const value = JSON.parse(storage?.getItem(key) || "[]");
    return Array.isArray(value) ? value.filter((item) => item && typeof item.id === "string") : [];
  } catch {
    return [];
  }
}

export function saveCounselorSessions(identity, sessions, storage = globalThis.localStorage) {
  const key = counselorSessionsKey(identity);
  if (!key) return;
  try { storage?.setItem(key, JSON.stringify(sessions)); } catch { /* Browsing can continue when storage is full. */ }
}
