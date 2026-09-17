/** 任务拆解的纯数据转换(不依赖 React / 网络),便于单测覆盖。 */

/**
 * 构造 POST /study/task-breakdown 的请求体。
 *
 * - 有 taskId: 让后端读取个人待办的说明、材料、截止时间、通知原文作为生成上下文,
 *   并据此触发校园政策检索。goal 可选——不填时后端直接用任务标题拆解。
 * - 无 taskId: 自由文本目标,保持原有行为。
 *
 * 两种情况下都不会把任务说明或通知原文回传给后端。
 */
export function buildBreakdownPayload({ taskId, goal }) {
  const trimmedGoal = typeof goal === "string" ? goal.trim() : "";
  if (taskId) {
    return trimmedGoal ? { task_id: taskId, goal: trimmedGoal } : { task_id: taskId };
  }
  return { goal: trimmedGoal };
}
