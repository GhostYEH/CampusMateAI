const completedSubmissionStatuses = new Set(["submitted", "graded", "late", "resubmitted"]);

function assignmentIsPending(item = {}) {
  if (item.is_remote) return !["completed", "closed"].includes(item.status);
  return !completedSubmissionStatuses.has(item.submission_status);
}

function deadlineOf(item = {}) {
  return item.deadline || item.due_at || item.due_date || null;
}

export function buildCourseRailItems(courses = [], assignments = []) {
  return (courses || []).map((course) => {
    const courseAssignments = (assignments || []).filter(
      (assignment) => String(assignment.course_id) === String(course.id) && assignmentIsPending(assignment),
    );
    const deadlines = courseAssignments
      .map((assignment) => deadlineOf(assignment))
      .filter(Boolean)
      .sort((a, b) => new Date(a).valueOf() - new Date(b).valueOf());
    return {
      id: course.id,
      name: course.name || course.title || "未命名课程",
      code: course.code || "",
      teacher: course.teacher_name || course.teacher || "教师信息待同步",
      term: course.semester || course.term || "学期待同步",
      pendingCount: courseAssignments.length,
      nextDeadline: deadlines[0] || null,
    };
  });
}

/**
 * 受管服务的状态 → 界面该说什么、该开哪些入口。
 *
 * 四种状态互斥，且**不把"取不到"说成"没有"**：
 * - disabled：融合开关关闭，网关根本没去连服务。
 * - unavailable：连不上/被拒，重试可能有意义。
 * - degraded：服务在线但依赖未就绪，重试无用，等运维。
 * - ready：能力集可信，按真实 capability 逐项开放。
 */
export const FUSION_STATES = ["disabled", "unavailable", "degraded", "ready"];

const FUSION_COPY = {
  disabled: {
    label: "未启用",
    detail: "本部署未启用受管 OpenMAIC 服务；已生成的课堂内容仍可查看。",
  },
  unavailable: {
    label: "暂时不可用",
    detail: "受管服务当前无法连接，可稍后重试；已有内容不受影响。",
  },
  degraded: {
    label: "部分能力未就绪",
    detail: "受管服务在线但依赖未就绪，相关入口已暂时关闭。",
  },
  ready: {
    label: "可用",
    detail: "受管服务与依赖均已就绪。",
  },
};

export function describeFusionState(status) {
  const state = FUSION_STATES.includes(status?.state) ? status.state : "unavailable";
  const copy = FUSION_COPY[state];
  const capabilities = state === "ready" && Array.isArray(status?.capabilities) ? status.capabilities : [];
  const has = (capability) => capabilities.includes(capability);
  return {
    state,
    label: copy.label,
    detail: copy.detail,
    capabilities,
    // 只有 ready 才允许出现可点击入口；其余状态一律关闭，避免点了必然失败。
    canCreateWorkspace: has("workspace"),
    canImport: has("import-pptx") || has("import-maic"),
    canSearch: has("search"),
    canBrowseFolders: has("folder"),
  };
}

/**
 * 把服务端返回的"最近内容"映射成视图模型。
 *
 * 服务端已按权限过滤并按 `updated_at` 倒序，这里**不再排序**：
 * 客户端重新排序会让"最近"与真实来源分叉。
 */
export function normalizeRecentItems(payload) {
  const items = Array.isArray(payload) ? payload : payload?.items;
  return (items || [])
    .filter((item) => item && item.id)
    .map((item) => ({
      id: item.id,
      kind: item.kind || "classroom",
      courseId: item.course_id,
      courseName: item.course_name || "课程上下文",
      title: item.title || "互动课堂",
      mode: item.mode || "",
      status: item.status || "",
      scenesCount: item.scenes_count ?? null,
      // 站内深链由服务端给出，保证与服务端权限口径一致。
      href: item.href || `/courses/${item.course_id}`,
      classroomUrl: item.classroom_url || null,
      classroomUrlUnavailableReason: item.classroom_url_unavailable_reason || null,
      createdAt: item.created_at || "",
      updatedAt: item.updated_at || item.created_at || "",
    }));
}

export function filterOpenMAICHomeItems(items = [], query = "") {
  const normalized = String(query || "").trim().toLocaleLowerCase();
  if (!normalized) return items;
  return items.filter((item) =>
    [item.title, item.name, item.courseName, item.course_name, item.code]
      .filter(Boolean)
      .join(" ")
      .toLocaleLowerCase()
      .includes(normalized),
  );
}
