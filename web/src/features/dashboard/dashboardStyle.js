export const DASHBOARD_STYLE_KEY = "campus_dashboard_style";

export function normalizeDashboardStyle(value) {
  return value === "gamified" ? "gamified" : "classic";
}

export function loadDashboardStyle(storage = globalThis.localStorage) {
  try {
    return normalizeDashboardStyle(storage?.getItem(DASHBOARD_STYLE_KEY));
  } catch {
    return "classic";
  }
}

export function persistDashboardStyle(storage, value) {
  const normalized = normalizeDashboardStyle(value);
  try {
    storage?.setItem(DASHBOARD_STYLE_KEY, normalized);
  } catch {
    // The reactive preference still works when storage is unavailable.
  }
  return normalized;
}
