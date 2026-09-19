import {
  DEFAULT_SELECTED_ROLE_IDS,
  normalizeSelectedRoleIds,
} from "./roleModel.js";

export const OPENMAIC_AGENT_SETTINGS_KEY = "campus_openmaic_agent_settings_v1";

const defaults = () => ({
  mode: "preset",
  selectedRoleIds: [...DEFAULT_SELECTED_ROLE_IDS],
});

export function normalizeOpenMAICAgentSettings(value) {
  const next = defaults();
  if (value?.mode === "auto" || value?.mode === "preset") next.mode = value.mode;
  if (Array.isArray(value?.selectedRoleIds)) next.selectedRoleIds = normalizeSelectedRoleIds(value.selectedRoleIds);
  return next;
}

export function loadOpenMAICAgentSettings(storage = globalThis.localStorage) {
  try {
    const raw = storage?.getItem(OPENMAIC_AGENT_SETTINGS_KEY);
    return raw ? normalizeOpenMAICAgentSettings(JSON.parse(raw)) : defaults();
  } catch {
    return defaults();
  }
}

export function saveOpenMAICAgentSettings(value, storage = globalThis.localStorage) {
  const normalized = normalizeOpenMAICAgentSettings(value);
  try {
    storage?.setItem(OPENMAIC_AGENT_SETTINGS_KEY, JSON.stringify(normalized));
  } catch {
    // Private browsing and embedded contexts may reject localStorage. The UI still works for this session.
  }
  return normalized;
}
