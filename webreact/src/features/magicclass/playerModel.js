/**
 * 播放器的视图模型。
 *
 * 播放器最容易"看起来能用其实不安全/不诚实"，所以三条规则在这里定死：
 *
 * 1. **只有 `sandbox-*` 才允许 iframe。** 原生场景由 CampusMate 自己渲染；
 *    服务端说 `unsupported` 时显示**具体缺什么**，而不是一块空白或一个死按钮。
 * 2. **sandbox 由服务端决定，前端不放大。** `allow-same-origin` 一旦与
 *    `allow-scripts` 同时出现，iframe 就能触达父文档，沙箱等于没有；这里再校验一次。
 * 3. **进度是 URL 的一部分。** `start_index` 来自服务端（由 `scene_id` 推导），
 *    刷新后回到同一个场景，而不是每次从头开始。
 */

export const PLAYER_SANDBOX = "allow-scripts";

export const RENDER_KINDS = ["native", "sandbox-html", "sandbox-url", "unsupported"];

const DEGRADE_COPY = {
  scene_type_unsupported: "这个场景的类型当前没有对应的渲染器。",
  widget_requires_external_cdn: "该互动内容需要外部 3D/CDN 能力，本部署未启用。",
  widget_type_unknown: "这个互动组件类型无法识别。",
  interactive_payload_missing: "该互动场景没有可播放的内容。",
};

/** 服务端给出的降级原因 → 界面文案。未知原因也要说清楚"是哪种未知"。 */
export function degradeNotice(scene) {
  const reason = scene?.render?.reason;
  if (!reason) return "这个场景当前无法播放。";
  return DEGRADE_COPY[reason] || `这个场景当前无法播放（${reason}）。`;
}

/**
 * 是否允许把该场景放进 iframe。
 *
 * 只有服务端明确给出 `sandbox-*` 且 sandbox 串里**不含** `allow-same-origin`
 * 时才允许；其余一律走原生渲染或降级提示。
 */
export function sandboxPolicyFor(render) {
  const kind = render?.kind;
  if (kind !== "sandbox-html" && kind !== "sandbox-url") {
    return { allowIframe: false, sandbox: "", kind: kind || "unsupported" };
  }
  const sandbox = String(render.sandbox || "");
  if (!sandbox || sandbox.split(/\s+/).includes("allow-same-origin")) {
    // 服务端若给出空串或放大了权限，前端拒绝执行比"照做"更安全。
    return { allowIframe: false, sandbox: "", kind: "unsupported" };
  }
  return { allowIframe: true, sandbox, kind };
}

export function normalizePlayback(payload) {
  const scenes = Array.isArray(payload?.scenes) ? payload.scenes : [];
  const normalized = scenes
    .filter((scene) => scene && scene.id)
    .map((scene) => ({
      id: scene.id,
      type: scene.type || "unknown",
      title: scene.title || "未命名场景",
      order: Number(scene.order) || 0,
      render: scene.render && typeof scene.render === "object" ? scene.render : { kind: "unsupported" },
      steps: Array.isArray(scene.steps) ? scene.steps : [],
      droppedActions: Array.isArray(scene.dropped_actions) ? scene.dropped_actions : [],
      whiteboards: Number(scene.whiteboards) || 0,
      multiAgent: Boolean(scene.multi_agent),
    }))
    .sort((a, b) => a.order - b.order);

  const startIndex = Math.min(Math.max(Number(payload?.start_index) || 0, 0), Math.max(normalized.length - 1, 0));

  return {
    stageId: payload?.stage_id || "",
    workspaceId: payload?.workspace_id || "",
    title: payload?.title || "未命名内容",
    revision: Number(payload?.revision) || 0,
    dslVersion: payload?.dsl_version || "",
    startIndex,
    scenes: normalized,
    degraded: Array.isArray(payload?.degraded) ? payload.degraded : [],
  };
}

/** 上一场景/下一场景的边界与进度。玩家只能停在真实存在的场景上。 */
export function playerNavigation(scenes, index) {
  const total = scenes.length;
  const safeIndex = total === 0 ? 0 : Math.min(Math.max(Number(index) || 0, 0), total - 1);
  return {
    index: safeIndex,
    total,
    hasPrev: safeIndex > 0,
    hasNext: total > 0 && safeIndex < total - 1,
    prevIndex: safeIndex > 0 ? safeIndex - 1 : null,
    nextIndex: total > 0 && safeIndex < total - 1 ? safeIndex + 1 : null,
    // 进度按"第几个 / 共几个"给出，避免在 0 个场景时除零。
    progress: total === 0 ? 0 : (safeIndex + 1) / total,
  };
}

/** 场景动作时间线：`sync` 步骤必须等前一步结束，`fire_and_forget` 不等。 */
export function actionTimeline(scene) {
  return (scene?.steps || []).map((step, index) => ({
    actionId: step.action_id || `step_${index}`,
    type: step.type || "unknown",
    blocking: step.mode !== "fire_and_forget",
  }));
}

/**
 * 播放失败语义。播放是只读的，所以这里没有"冲突"分支：要么读到，要么读不到，
 * 要么服务没就绪。
 */
export function describePlaybackError(error) {
  const status = error?.response?.status;
  const code = error?.response?.data?.code;
  const detail = error?.response?.data?.message;

  if (code === "MAGICCLASS_FUSION_UNAVAILABLE" || status === 503) {
    return { kind: "unavailable", retryable: true, message: detail || "受管服务当前不可用，请稍后重试。" };
  }
  if (code === "MAGICCLASS_WORKSPACE_NOT_FOUND" || status === 404) {
    return { kind: "notFound", retryable: false, message: detail || "该内容不存在，可能已被删除。" };
  }
  if (status === 400 || code === "MAGICCLASS_INVALID_REQUEST") {
    return { kind: "invalid", retryable: false, message: detail || "请求不合法。" };
  }
  return { kind: "unknown", retryable: true, message: detail || "无法打开播放器，请稍后重试。" };
}
