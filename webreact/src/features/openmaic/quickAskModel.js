/**
 * 「快速询问」的决策模型。
 *
 * 两条产品事实决定了这里的实现，缺一条就会重演"点一下就整页 503"：
 *
 * 1. **课程 OpenMAIC 生成必须进入工作台。** 这条入口不是校园助手的快捷链接；
 *    工作台负责持久化生成内容、恢复场景和继续编辑，所以不能降级成 `/counselor`。
 * 2. **绑定失败不是页级错误。** 它只影响这一次绑定，返回的是可展示的局部文案
 *    与下一步动作，不写入页面级 error。
 */
import { describeWorkspaceError } from "./workspaceModel.js";

/**
 * OpenMAIC 工作台深链。工作台 id 是服务端真实创建/复用的结果，禁止客户端猜造。
 */
export function workspaceHref(courseId, workspaceId, prompt, { mode = "preset", selectedRoleIds = [] } = {}) {
  if (!courseId || !workspaceId) throw new Error("打开 OpenMAIC 工作台需要真实的课程和工作台");
  const parts = [`prompt=${encodeURIComponent(prompt || "")}`, `mode=${encodeURIComponent(mode)}`];
  if (selectedRoleIds.length) parts.push(`roles=${encodeURIComponent(selectedRoleIds.join(","))}`);
  return `/courses/${encodeURIComponent(courseId)}/workspaces/${encodeURIComponent(workspaceId)}?${parts.join("&")}`;
}

/**
 * The reference OpenMAIC flow always shows a generation preview before any
 * durable workspace is touched. Keep the complete launch context in the URL
 * so refresh/back navigation cannot silently lose the user's choices.
 */
export function generationPreviewHref(courseId, prompt, { mode = "preset", selectedRoleIds = [], webSearch = false } = {}) {
  if (!courseId) throw new Error("打开 OpenMAIC 预览需要真实的课程");
  const parts = [
    `prompt=${encodeURIComponent(prompt || "")}`,
    `mode=${encodeURIComponent(mode)}`,
    `roles=${encodeURIComponent(selectedRoleIds.join(","))}`,
  ];
  if (webSearch) parts.push("web=1");
  return `/courses/${encodeURIComponent(courseId)}/openmaic-preview?${parts.join("&")}`;
}

/**
 * 快速询问要不要先绑定工作台。
 *
 * 只有服务端**真实上报**了 `workspace` 能力（即 `state === "ready"`）时才尝试。
 * disabled / unavailable / degraded 都不能伪装成已成功进入工作台；入口应显示局部
 * 可操作错误，让用户在服务恢复后重试。
 */
export function shouldBindWorkspace(fusionView) {
  return Boolean(
    fusionView?.canCreateWorkspace &&
    Array.isArray(fusionView?.capabilities) &&
    fusionView.capabilities.includes("generation"),
  );
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
 * `fallbackLabel` 保留为兼容字段，但课程页不再把它渲染成校园助手跳转。
 */
export function describeQuickAskFailure(error) {
  const described = describeWorkspaceError(error);
  return {
    kind: described.kind,
    reason: described.reason || "unknown",
    retryable: described.retryable,
    message: described.message,
    fallbackLabel: "服务恢复后重试",
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
