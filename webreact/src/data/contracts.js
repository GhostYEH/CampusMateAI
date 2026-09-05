export function itemsOf(value) {
  if (Array.isArray(value)) return value;
  return Array.isArray(value?.items) ? value.items : [];
}

export function normalizeNotice(item = {}) {
  return {
    ...item,
    has_read: typeof item.has_read === "boolean" ? item.has_read : !Boolean(item.unread),
    published_at: item.published_at || item.time || item.created_at || null,
    source: item.source || item.source_name || item.course_name || "",
  };
}

export function studySessionPayload({ goal, mode = "quiet", minutes = null } = {}) {
  const experienceMode = {
    deep: "SMART_GUARD",
    steady: "AI_COMPANION",
    quiet: "QUIET",
  }[mode] || "QUIET";
  return {
    mode: "focus",
    experience_mode: experienceMode,
    ...(minutes ? { planned_duration_seconds: Math.round(Number(minutes) * 60) } : {}),
    ...(goal ? { goal } : {}),
  };
}

export function submissionPayload(textContent, submit = false) {
  return { text_content: textContent, submit: Boolean(submit) };
}
