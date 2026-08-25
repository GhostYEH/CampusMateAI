const DAY = 24 * 60 * 60 * 1000;

function toDate(value) {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.valueOf()) ? null : date;
}

function isSameDay(left, right) {
  return left && right && left.getFullYear() === right.getFullYear()
    && left.getMonth() === right.getMonth()
    && left.getDate() === right.getDate();
}

function priorityLabel(priority) {
  return { high: "高", medium: "中", low: "低" }[priority] || "中";
}

function importanceLabel(importance) {
  return { urgent: "紧急", high: "学业关键", important: "较重要", normal: "普通", low: "次要", unknown: "待评" }[importance] || "待评";
}

function assignmentDone(item) {
  return ["submitted", "graded"].includes(item.submission_status);
}

export function buildTaskModel(assignments = [], personal = []) {
  return [
    ...assignments.map((item) => ({
      ...item,
      id: `assignment-${item.id}`,
      sourceId: item.id,
      kind: "assignment",
      typeLabel: "课程作业",
      done: assignmentDone(item),
      priority: item.priority || (item.submission_status === "overdue" ? "high" : "medium"),
      source: [item.course_name, item.class_name].filter(Boolean).join(" · ") || "课程作业",
      statusLabel: item.submission_status === "graded" ? "已评分" : item.submission_status === "submitted" ? "已提交" : item.submission_status === "overdue" ? "已逾期" : "待完成",
      progress: item.submission_status === "graded" ? 100 : item.submission_status === "submitted" ? 70 : 0,
    })),
    ...personal.map((item) => ({
      ...item,
      id: `personal-${item.id}`,
      sourceId: item.id,
      kind: "personal",
      typeLabel: "个人待办",
      done: item.status === "completed",
      priority: item.priority || "medium",
      importance: item.importance || "unknown",
      source: item.source_name || "个人安排",
      statusLabel: item.status === "completed" ? "已完成" : "待完成",
      progress: item.status === "completed" ? 100 : 0,
    })),
  ];
}

export function getTaskMetrics(tasks = [], now = new Date()) {
  const current = toDate(now) || new Date();
  const pending = tasks.filter((task) => !task.done);
  const completed = tasks.filter((task) => task.done);
  const today = pending.filter((task) => isSameDay(toDate(task.deadline), current));
  const upcoming = pending.filter((task) => {
    const due = toDate(task.deadline);
    return due && due >= current && due.getTime() - current.getTime() <= 2 * DAY;
  });
  const overdue = pending.filter((task) => {
    const due = toDate(task.deadline);
    return due && due < current;
  });
  return {
    total: tasks.length,
    pending: pending.length,
    completed: completed.length,
    today: today.length,
    upcoming: upcoming.length,
    overdue: overdue.length,
    completionRate: tasks.length ? Math.round((completed.length / tasks.length) * 100) : 0,
  };
}

export function getTaskState(task, now = new Date()) {
  if (task.done) return "completed";
  const due = toDate(task.deadline);
  const current = toDate(now) || new Date();
  if (due && due < current) return "overdue";
  if (due && isSameDay(due, current)) return "today";
  if (due && due.getTime() - current.getTime() <= 7 * DAY) return "upcoming";
  return "later";
}

export function filterAndSortTasks(tasks = [], filters = {}, now = new Date()) {
  const query = String(filters.query || "").trim().toLocaleLowerCase();
  const result = tasks.filter((task) => {
    const matchesQuery = !query || `${task.title} ${task.source} ${task.typeLabel}`.toLocaleLowerCase().includes(query);
    const matchesKind = !filters.kind || filters.kind === "all" || task.kind === filters.kind;
    const matchesStatus = !filters.status || filters.status === "all"
      || (filters.status === "done" ? task.done : filters.status === "pending" ? !task.done : getTaskState(task, now) === filters.status);
    return matchesQuery && matchesKind && matchesStatus;
  });
  const direction = filters.sort === "latest" ? -1 : 1;
  return result.sort((left, right) => {
    if (filters.sort === "title") return left.title.localeCompare(right.title, "zh-CN") * direction;
    const leftDue = toDate(left.deadline)?.getTime() ?? Number.MAX_SAFE_INTEGER;
    const rightDue = toDate(right.deadline)?.getTime() ?? Number.MAX_SAFE_INTEGER;
    return (leftDue - rightDue) * direction;
  });
}

export function groupTasks(tasks = [], now = new Date()) {
  const groups = { today: [], upcoming: [], later: [], completed: [], overdue: [] };
  tasks.forEach((task) => groups[getTaskState(task, now)].push(task));
  return groups;
}

export function formatDeadline(value, options = {}) {
  const date = toDate(value);
  if (!date) return "未设置截止时间";
  const { withYear = false } = options;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    ...(withYear ? { year: "numeric" } : {}),
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function getPriorityLabel(priority) {
  return priorityLabel(priority);
}

export function getImportanceLabel(importance) {
  return importanceLabel(importance);
}

export function getRemainingSeconds(value, now = new Date()) {
  const deadline = toDate(value);
  const current = toDate(now) || new Date();
  if (!deadline) return null;
  return Math.max(0, Math.floor((deadline.getTime() - current.getTime()) / 1000));
}
