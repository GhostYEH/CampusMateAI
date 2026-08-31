function timestamp(value) {
  if (!value) return Number.POSITIVE_INFINITY;
  const parsed = new Date(value).getTime();
  return Number.isNaN(parsed) ? Number.POSITIVE_INFINITY : parsed;
}

function examTimestamp(exam) {
  if (!exam?.exam_date) return Number.NaN;
  return new Date(`${exam.exam_date}T${exam.end_time || exam.start_time || "23:59"}`).getTime();
}

export function todayScheduleItems(items, now = new Date()) {
  const weekday = now.getDay() || 7;
  return (items || [])
    .filter((item) => !item?.is_stale && Number(item?.weekday) === weekday)
    .sort((left, right) => Number(left.start_section || 0) - Number(right.start_section || 0));
}

export function buildDueItems(dashboard) {
  return [
    ...(dashboard?.due_soon_assignments || []).map((item) => ({
      ...item,
      kind: "作业",
      due: item.deadline,
      icon: "PhFileText",
      tone: "red",
      sourceType: "assignment",
      route: `/tasks/assignment/${item.id}`,
    })),
    ...(dashboard?.due_soon_personal_tasks || []).map((item) => ({
      ...item,
      kind: "待办",
      due: item.deadline,
      icon: "PhCheckSquare",
      tone: "amber",
      sourceType: "personal-task",
      route: `/tasks/personal/${item.id}`,
    })),
  ].sort((left, right) => timestamp(left.due) - timestamp(right.due)).slice(0, 6);
}

export function selectUpcomingExam(exams, now = new Date()) {
  const current = now.getTime();
  return (exams || [])
    .map((exam) => ({ exam, at: examTimestamp(exam) }))
    .filter(({ at }) => Number.isFinite(at) && at >= current)
    .sort((left, right) => left.at - right.at)[0]?.exam || null;
}

function sectionLabel(item) {
  const start = item.start_section;
  const end = item.end_section ?? start;
  if (!start) return "时间待定";
  return start === end ? `第 ${start} 节` : `第 ${start}-${end} 节`;
}

export function buildMainQuests({ scheduleItems = [], dueItems = [], exams = [] } = {}, now = new Date()) {
  const courses = todayScheduleItems(scheduleItems, now).map((item) => ({
    id: `course:${item.id || `${item.course_name}-${item.start_section}`}`,
    sourceId: String(item.id || ""),
    sourceType: "course",
    title: item.course_name || "未命名课程",
    meta: [sectionLabel(item), item.location].filter(Boolean).join(" · "),
    icon: "PhBookOpen",
    route: "/academic",
  }));

  const deadlines = dueItems.slice(0, 3).map((item) => ({
    id: `${item.sourceType || "task"}:${item.id}`,
    sourceId: String(item.id || ""),
    sourceType: item.sourceType || "task",
    title: item.title || "未命名任务",
    meta: item.due || "未设置截止时间",
    icon: item.icon || "PhCheckSquare",
    route: item.route || "/tasks",
  }));

  const exam = selectUpcomingExam(exams, now);
  const examQuest = exam ? [{
    id: `exam:${exam.id}`,
    sourceId: String(exam.id || ""),
    sourceType: "exam",
    title: exam.course_name || "考试安排",
    meta: [exam.exam_date, exam.start_time, exam.location].filter(Boolean).join(" · "),
    icon: "PhExam",
    route: "/exams",
  }] : [];

  return [...courses, ...deadlines, ...examQuest];
}
