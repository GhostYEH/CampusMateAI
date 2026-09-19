/**
 * 「快速询问」的决策模型。
 *
 * 两条产品事实决定了这里的实现，缺一条就会重演"点一下就整页 503"：
 *
 * 1. **课程辅导本身不依赖学习工作台。** `/counselor?course=…` 只要课程上下文就能
 *    工作，工作台只是"继续追问"的上下文绑定。所以受管服务没就绪时，正确做法是
 *    **不发** `GET /workspaces` 直接进入课程辅导，而不是把一次必然失败的请求
 *    塞进用户的主流程。
 * 2. **绑定失败不是页级错误。** 它只影响这一次绑定，返回的是可展示的局部文案
 *    与下一步动作，不写入页面级 error。
 */
import { describeWorkspaceError } from "./workspaceModel.js";

/**
 * 课程辅导深链。
 *
 * `workspaceId` 为空时只带课程上下文——**不伪造**工作台关联：辅导页会如实显示
 * "已定向到课程上下文"。
 */
export function counselorHref(courseId, prompt, workspaceId = null) {
  const parts = [];
  if (courseId) parts.push(`course=${encodeURIComponent(courseId)}`);
  if (workspaceId) parts.push(`workspace=${encodeURIComponent(workspaceId)}`);
  if (prompt) parts.push(`prompt=${encodeURIComponent(prompt)}`);
  return `/counselor?${parts.join("&")}`;
}

/**
 * 快速询问要不要先绑定工作台。
 *
 * 只有服务端**真实上报**了 `workspace` 能力（即 `state === "ready"`）时才尝试。
 * disabled / unavailable / degraded 一律直接进入课程辅导——那些状态下能力列表
 * 是空的，先请求一次只会拿到 503。
 */
export function shouldBindWorkspace(fusionView) {
  return Boolean(fusionView?.canCreateWorkspace);
}

/**
 * 复用已有工作台。
 *
 * 取列表里第一个就够：快速询问不是工作台管理器，多出来的选择留给工作台面板。
 * 返回 `null` 表示该课程还没有工作台，调用方需要创建一个。
 */
export function pickReusableWorkspace(payload) {
  const items = Array.isArray(payload) ? payload : payload?.items;
  const first = (items || []).find((item) => item && item.id);
  return first ? { id: first.id, name: first.name || "" } : null;
}

/**
 * 把绑定失败翻译成局部文案与可行动作。
 *
 * `fallbackLabel` 恒非空：课程辅导始终可以走，绑定失败不应该让用户问不出问题。
 */
export function describeQuickAskFailure(error) {
  const described = describeWorkspaceError(error);
  return {
    kind: described.kind,
    reason: described.reason || "unknown",
    retryable: described.retryable,
    message: described.message,
    fallbackLabel: "不绑定工作台，直接进入课程辅导",
  };
}

/**
 * 提交前的本地校验。返回 `null` 表示可以提交。
 *
 * 放在这里而不是散在组件里，是因为"能不能提交"必须与按钮的 disabled 条件同源，
 * 否则会出现"按钮亮着但点了没反应"。
 */
export function quickAskRejection({ query, courseId, busy } = {}) {
  if (busy) return "正在处理上一次请求，请稍候。";
  if (!String(courseId || "")) return "请先选择一门课程。";
  if (!String(query || "").trim()) return "请输入你想问的问题。";
  return null;
}
