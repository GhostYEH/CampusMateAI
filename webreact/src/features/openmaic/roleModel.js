/**
 * CampusMate's small, course-facing copy of OpenMAIC's classroom roster.
 *
 * These are selectable classroom participants, not CampusMate account roles.
 * The teacher is always present; the remaining participants can be toggled in
 * preset mode. Auto mode leaves the roster to the OpenMAIC generator.
 */
export const OPENMAIC_AGENT_ROLES = [
  { id: "default-1", name: "AI教师", role: "教师", short: "教", color: "#3b82f6", required: true },
  { id: "default-2", name: "AI助教", role: "助教", short: "助", color: "#10b981", required: false },
  { id: "default-3", name: "显眼包", role: "学生", short: "显", color: "#f59e0b", required: false },
  { id: "default-4", name: "好奇宝宝", role: "学生", short: "奇", color: "#ec4899", required: false },
  { id: "default-5", name: "笔记员", role: "学生", short: "记", color: "#06b6d4", required: false },
  { id: "default-6", name: "思考者", role: "学生", short: "思", color: "#8b5cf6", required: false },
];

export const DEFAULT_SELECTED_ROLE_IDS = ["default-1", "default-3", "default-4"];

export function normalizeSelectedRoleIds(ids) {
  const known = new Set(OPENMAIC_AGENT_ROLES.map((role) => role.id));
  const selected = Array.isArray(ids) ? ids.filter((id) => known.has(id)) : [];
  const withoutDuplicates = [...new Set(selected)];
  return [
    "default-1",
    ...withoutDuplicates.filter((id) => id !== "default-1"),
  ];
}

export function selectedRoles(ids) {
  const selected = new Set(normalizeSelectedRoleIds(ids));
  return OPENMAIC_AGENT_ROLES.filter((role) => selected.has(role.id));
}
