function recordKey(item = {}) {
  return item.external_id ?? item.externalId ?? item.id ?? `${item.kind || "record"}:${item.title ?? ""}:${item.deadline ?? ""}`;
}

export function normalizeRemoteNotice(item = {}) {
  return {
    ...item,
    is_remote: true,
    has_read: item.has_read ?? true,
    content: item.content || item.body || item.description || "",
  };
}

export function isCompletedSubmissionStatus(status) {
  return ["submitted", "graded", "late", "resubmitted"].includes(status);
}

export function taskAssignmentStatusLabel(status) {
  return { graded: "已评分", submitted: "已提交", late: "已提交（逾期）", resubmitted: "已重新提交" }[status] || "未提交";
}

export function taskAssignmentProgress(status) {
  return isCompletedSubmissionStatus(status) ? 100 : 0;
}

export function taskGroupState(task = {}, now = new Date()) {
  if (task.done) return "completed";
  const current = now instanceof Date ? now : new Date(now);
  const deadline = task.deadline ? new Date(task.deadline) : null;
  if (!deadline || Number.isNaN(deadline.valueOf()) || Number.isNaN(current.valueOf())) return "later";
  if (deadline < current) return "overdue";
  if (deadline.toDateString() === current.toDateString()) return "today";
  if (deadline.getTime() - current.getTime() <= 7 * 86400000) return "upcoming";
  return "later";
}

export function buildHomeSearchResults(data = {}, query = "") {
  const normalized = String(query || "").trim().toLocaleLowerCase();
  if (!normalized) return [];
  const matches = (value) => String(value || "").toLocaleLowerCase().includes(normalized);
  return [
    ...(data.courses || []).filter((item) => matches(`${item.name || ""} ${item.code || ""}`)).map((item) => ({ ...item, resultKind: "课程", resultTitle: item.name || "课程", resultDetail: item.code || "课程详情", resultRoute: `/courses/${item.id}` })),
    ...(data.assignments || []).filter((item) => matches(`${item.title || ""} ${item.course_name || ""} ${item.class_name || ""}`)).map((item) => ({ ...item, resultKind: "作业", resultTitle: item.title || "课程作业", resultDetail: item.course_name || item.class_name || "课程作业", resultRoute: `/tasks/assignment/${item.id}` })),
    ...(data.tasks || []).filter((item) => matches(`${item.title || ""} ${item.description || ""}`)).map((item) => ({ ...item, resultKind: "待办", resultTitle: item.title || "个人待办", resultDetail: item.source_name || "个人安排", resultRoute: `/tasks/personal/${item.id}` })),
    ...(data.notices || []).filter((item) => matches(`${item.title || ""} ${item.content || item.body || item.description || ""}`)).map((item) => ({ ...item, resultKind: "通知", resultTitle: item.title || "校园通知", resultDetail: item.source || "校园通知", resultRoute: "/notifications" })),
  ].slice(0, 10);
}

export function assignmentStatusLabel(item = {}) {
  if (item.is_remote) {
    return { completed: "已完成", closed: "已结束" }[item.status] || "未完成";
  }
  return { draft: "草稿", submitted: "已提交", resubmitted: "已重新提交", late: "已提交（逾期）", graded: "已评分" }[item.submission_status] || "可提交";
}

export function isLocalGradeAssignment(item = {}) {
  return !item.is_remote;
}

export function submissionStatusLabel(status) {
  return { draft: "草稿", submitted: "已提交", late: "已提交（逾期）", resubmitted: "已重新提交", graded: "已评分" }[status] || "未提交";
}

export function submissionActionLabel(status) {
  return ["submitted", "late", "resubmitted"].includes(status) ? "重新提交" : "提交作业";
}

export function shouldFinalizeSubmission(saved = {}) {
  return Boolean(saved?.id && saved.status === "draft");
}

const completedSubmissionStatuses = new Set(["submitted", "graded", "late", "resubmitted"]);

export function courseProgress(course = {}, assignments = []) {
  const courseAssignments = (assignments || []).filter((item) => String(item.course_id) === String(course.id));
  if (!courseAssignments.length) return 0;
  return Math.round(courseAssignments.filter((item) => completedSubmissionStatuses.has(item.submission_status)).length / courseAssignments.length * 100);
}

export function courseMaterialCount(course = {}) {
  return Number(course.material_count ?? course.resource_count ?? course.materials_count ?? 0);
}

export function weeklyTrend(records = [], now = new Date(), dateField = "completed_at", valueOf = () => 1) {
  const end = now instanceof Date ? new Date(now) : new Date(now);
  end.setHours(0, 0, 0, 0);
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(end);
    date.setDate(end.getDate() - 6 + index);
    const count = (records || []).filter((item) => {
      const value = item?.[dateField] || item?.started_at || item?.updated_at;
      const recordDate = value ? new Date(value) : null;
      return recordDate && !Number.isNaN(recordDate.valueOf()) && recordDate.toDateString() === date.toDateString();
    }).reduce((total, item) => total + Number(valueOf(item) || 0), 0);
    return { label: ["日", "一", "二", "三", "四", "五", "六"][date.getDay()], date: date.toISOString().slice(0, 10), count };
  });
}

export function filterActiveSchedule(items = []) {
  return (items || []).filter((item) => !item?.is_stale);
}

export function isChaoxingConnected(data = {}) {
  return Boolean(data.connected || data.authenticated || ["online", "connected"].includes(data.status));
}

export function chaoxingSyncSummary(result = {}) {
  const stats = result.stats || {};
  const number = (...values) => {
    const value = values.find((candidate) => candidate != null);
    return Number(value || 0);
  };
  return {
    complete: result.complete !== false,
    courses: number(stats.courses_fetched, result.courses),
    teachers: number(stats.teachers_fetched, result.teachers),
    pendingAssignments: number(stats.assignments_pending, result.pending_assignments),
    notices: number(stats.notices_fetched, result.notices),
  };
}

export function qrStatusState(status) {
  if (status === "CONSUMED") return { state: "error", error: "二维码已被使用，请重新生成" };
  if (status === "EXPIRED") return { state: "expired", error: "" };
  if (status === "CANCELLED") return { state: "cancelled", error: "" };
  if (status === "SCANNED") return { state: "scanned", error: "" };
  if (status === "CONFIRMED") return { state: "confirmed", error: "" };
  return { state: "pending", error: "" };
}

export function examDetailFields(exam = {}) {
  return [
    { label: "类型", value: exam.exam_type || "考试" },
    { label: "备注", value: exam.notes || "暂无备注" },
    { label: "提醒", value: exam.reminder_enabled ? "已开启" : "未开启" },
  ];
}

export function noticeTaskDraft(extracted = {}) {
  const task = extracted.tasks?.[0] || extracted;
  return {
    title: task.task || task.title || "",
    deadline: task.deadline || "",
    submission_method: task.submission_method || "",
  };
}

export function updateNoticeTaskDraft(extracted = {}, field, value) {
  if (Array.isArray(extracted.tasks) && extracted.tasks.length) {
    const task = { ...extracted.tasks[0], [field]: value };
    if (field === "title") task.task = value;
    return { ...extracted, tasks: [task, ...extracted.tasks.slice(1)] };
  }
  const key = field === "title" && extracted.task ? "task" : field;
  return { ...extracted, [key]: value };
}

export function studyExperienceModel(view, context = {}) {
  return { view, ...context, title: context.title || "学习陪伴", value: context.value || "" };
}

export function mergeRecords(primary = [], secondary = []) {
  const result = [];
  const indexes = new Map();
  [...primary, ...secondary].forEach((item) => {
    if (!item) return;
    const key = recordKey(item);
    const index = indexes.get(key);
    if (index == null) {
      indexes.set(key, result.length);
      result.push({ ...item });
      return;
    }
    // Keep locally enriched state (submission/read status) while filling any
    // fields that only exist in the synchronized course record.
    result[index] = { ...item, ...result[index] };
  });
  return result;
}

export function buildContentTree(items = []) {
  const nodes = items.filter(Boolean).map((item) => ({ ...item, children: [] }));
  const byKey = new Map(nodes.map((item) => [String(item.external_id ?? item.id), item]));
  const roots = [];
  nodes.forEach((node) => {
    const parentKey = node.parent_external_id ?? node.parent_id ?? node.parent_content_id;
    const parent = parentKey == null ? null : byKey.get(String(parentKey));
    if (parent) parent.children.push(node);
    else roots.push(node);
  });
  return roots;
}

export function buildCommentTree(comments = []) {
  const nodes = comments.filter(Boolean).map((comment) => ({ ...comment, children: [] }));
  const byId = new Map(nodes.map((comment) => [String(comment.id), comment]));
  const roots = [];
  nodes.forEach((comment) => {
    const parentId = comment.parent_comment_id ?? comment.parent_id;
    const parent = parentId == null ? null : byId.get(String(parentId));
    if (parent) parent.children.push(comment);
    else roots.push(comment);
  });
  return roots;
}

export function isRenamedDuplicate(draft = {}) {
  if (!draft.existing_task_id) return false;
  return String(draft.title || "").trim() === String(draft.original_title || "").trim();
}
