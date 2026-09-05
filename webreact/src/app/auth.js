export const AUTH_KEYS = ["campus_session", "campus_access_token", "campus_refresh_token"];

export function clearStoredSession(storage = globalThis.localStorage) {
  AUTH_KEYS.forEach((key) => storage.removeItem(key));
}

export function readStoredSession(storage = globalThis.localStorage) {
  const token = storage.getItem("campus_access_token");
  const raw = storage.getItem("campus_session");
  if (!token || !raw) {
    if (raw && !token) storage.removeItem("campus_session");
    return null;
  }
  try {
    const session = JSON.parse(raw);
    if (!session || typeof session !== "object") throw new Error("Invalid session");
    if (session.role !== "student") {
      clearStoredSession(storage);
      return null;
    }
    return session;
  } catch {
    storage.removeItem("campus_session");
    return null;
  }
}

export function isAllowedSession(session, accessToken) {
  return Boolean(session && session.role === "student" && accessToken);
}
