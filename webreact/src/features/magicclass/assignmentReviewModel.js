import { itemsOf, userErrorMessage } from "../../data/contracts.js";

const errors = {
  assignment_not_ended: "作业尚未截止，截止后再来练习。",
  assignment_deadline_unknown: "尚未取得有效截止时间，请同步学习通后重试。",
  assignment_course_unavailable: "作业暂未关联课程，请重新同步学习通。",
  assignment_content_not_current: "还没有取得提交后的题目，请先同步作业。",
  assignment_images_require_text: "题目包含尚未识别的图片，暂时无法生成完整讲解。",
  assignment_content_too_large: "这份作业内容较长，超出了单次课堂可处理的范围。",
  chaoxing_assignment_not_found: "这份作业已不存在，请刷新列表。",
  sync_in_progress: "学习通正在同步，请稍后再次进入讲解。",
};

function errorCode(error) {
  return error?.response?.data?.detail || error?.response?.data?.message || error?.message;
}

export function assignmentReviewError(error) {
  return errors[errorCode(error)] || userErrorMessage(error, "课堂服务暂时不可用，请稍后重试。");
}

function assignmentDeadlineTime(task) {
  let deadline = String(task?.deadline || "").trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(deadline)) deadline += "T23:59:59+08:00";
  else if (/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(deadline)) deadline += "+08:00";
  return Date.parse(deadline);
}

export function assignmentHasEnded(task, now = Date.now()) {
  const endsAt = assignmentDeadlineTime(task);
  return Number.isFinite(endsAt) && endsAt <= now;
}

export async function loadEndedAssignments(getTasks, now = Date.now()) {
  const tasks = [];
  let page = 1;
  while (true) {
    const result = await getTasks({ page, page_size: 200 });
    const items = itemsOf(result);
    tasks.push(...items.filter((task) => task.source === "chaoxing" && ["pending", "completed"].includes(task.status) && !task.deleted_at && assignmentHasEnded(task, now)));
    if (!result?.has_more || !items.length) break;
    page += 1;
  }
  const time = (task) => assignmentDeadlineTime(task) || 0;
  return [...new Map(tasks.map((task) => [task.id, task])).values()].sort((a, b) => time(b) - time(a));
}

function waitForPoll(signal) {
  return new Promise((resolve) => {
    if (signal.aborted) { resolve(); return; }
    const finish = () => { clearTimeout(timer); signal.removeEventListener("abort", finish); resolve(); };
    const timer = setTimeout(finish, 2000);
    signal.addEventListener("abort", finish, { once: true });
  });
}

/** Resume the server's idempotent review and return only a completed lesson. */
export async function enterAssignmentReview(taskId, api, { signal, onPhase, wait = waitForPoll }) {
  let result;
  try {
    result = await api.generateChaoxingAssignmentClassroom(taskId);
  } catch (error) {
    if (signal.aborted) return null;
    if (errorCode(error) !== "assignment_content_not_current") throw error;
    onPhase({ state: "syncing" });
    await api.syncChaoxing();
    if (signal.aborted) return null;
    result = await api.generateChaoxingAssignmentClassroom(taskId);
  }
  if (signal.aborted) return null;
  if (!result?.course_id || !result?.workspace_id || !result?.job?.id) throw new Error("课堂未返回有效的生成任务，请重试。");
  let job = result.job;
  if (["failed", "cancelled"].includes(job.status)) {
    onPhase({ state: "retrying" });
    job = await api.retryMagicClassJob(result.course_id, job.id);
    if (signal.aborted) return null;
  }
  const deadline = Date.now() + 30 * 60 * 1000;
  while (["queued", "running"].includes(job.status)) {
    if (Date.now() >= deadline) throw new Error("课堂仍在生成，可以稍后再次点击，继续查看同一任务。");
    onPhase({ state: "generating", progress: Math.max(0, Math.min(100, Number(job.progress) || 0)) });
    await wait(signal);
    if (signal.aborted) return null;
    job = await api.getMagicClassJob(result.course_id, job.id);
    if (signal.aborted) return null;
  }
  if (job.status !== "completed") throw new Error("本次课堂生成未完成，请再次点击重试。");
  return `/courses/${encodeURIComponent(result.course_id)}/workspaces/${encodeURIComponent(result.workspace_id)}?mode=playback`;
}
