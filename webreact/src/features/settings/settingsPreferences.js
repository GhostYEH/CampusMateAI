export const SETTING_KEYS = {
  theme: "campus_theme",
  dashboardStyle: "campus_dashboard_style",
  reduceMotion: "campus_reduce_motion",
  compactList: "campus_compact_list",
  noticeReminder: "campus_notice_reminder",
  examReminder: "campus_exam_reminder",
  taskDue: "campus_task_due",
  announcementNotify: "campus_announcement_notify",
  autoplayVoice: "campus_autoplay_voice",
  shareFocusStats: "campus_share_focus_stats",
  showOnline: "campus_show_online",
};

export const DEFAULT_PREFERENCES = {
  theme: "auto",
  compactList: false,
  noticeReminder: true,
  examReminder: true,
  taskDue: true,
  announcementNotify: true,
  autoplayVoice: false,
  shareFocusStats: false,
  showOnline: true,
};

export function readPreference(key, fallback) {
  if (typeof window === "undefined") return fallback;
  const stored = window.localStorage.getItem(key);
  return stored === null ? fallback : stored === "true";
}

export function readPreferences() {
  if (typeof window === "undefined") return { ...DEFAULT_PREFERENCES };
  return Object.fromEntries(Object.entries(DEFAULT_PREFERENCES).map(([name, fallback]) => {
    const key = SETTING_KEYS[name];
    if (name === "theme") {
      return [name, window.localStorage.getItem(key) || fallback];
    }
    return [name, readPreference(key, fallback)];
  }));
}

export function persistPreference(name, value) {
  const key = SETTING_KEYS[name];
  if (key) window.localStorage.setItem(key, String(value));
}
