const courseNameCollator = new Intl.Collator("zh-CN", { numeric: true, sensitivity: "base" });

const dateFields = ["last_synced_at", "updated_at", "created_at"];

export function getCourseDateValue(course) {
  for (const field of dateFields) {
    const value = Date.parse(String(course?.[field] || ""));
    if (Number.isFinite(value)) return value;
  }
  return 0;
}

export function sortCourses(courses, sort = "name-asc") {
  const direction = sort.endsWith("-desc") ? -1 : 1;
  const compare = sort.startsWith("date-")
    ? (a, b) => getCourseDateValue(a) - getCourseDateValue(b)
    : (a, b) => courseNameCollator.compare(String(a?.name || ""), String(b?.name || ""));

  return [...courses].sort((a, b) => {
    const result = compare(a, b) * direction;
    if (result !== 0) return result;
    return courseNameCollator.compare(String(a?.name || ""), String(b?.name || ""));
  });
}
