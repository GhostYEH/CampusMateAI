/**
 * 小型、无副作用的课堂动作时间线。
 *
 * 播放计划只提供动作 id、类型和次序；真正的参数只能从已经授权读取的 scene.actions
 * 取回。这里不负责渲染或计时，调用者每一拍调用一次 `advanceActionTimeline`，再把
 * 返回的 effect 交给已有的画布 store。因此暂停、场景切换和单测都不会依赖 DOM。
 */

const EXECUTABLE_TYPES = new Set(["spotlight", "laser", "play_video"]);

export function isPlaybackShortcutTarget(target) {
  if (!target || typeof target !== "object") return false;
  if (target.isContentEditable) return true;
  const tagName = String(target.tagName || "").toUpperCase();
  if (["INPUT", "TEXTAREA", "SELECT"].includes(tagName)) return true;
  return typeof target.closest === "function"
    && Boolean(target.closest('[contenteditable="true"], input, textarea, select, [role="slider"], input[type="range"]'));
}

function actionIndex(scene) {
  return new Map(
    (Array.isArray(scene?.actions) ? scene.actions : [])
      .filter((action) => action && typeof action.id === "string")
      .map((action) => [action.id, action]),
  );
}

function elementIds(scene) {
  const elements = scene?.content?.type === "slide" && Array.isArray(scene.content.canvas?.elements)
    ? scene.content.canvas.elements
    : [];
  return new Set(elements.map((element) => element?.id).filter((id) => typeof id === "string" && id));
}

/** Begin a scene-local session. `clearEffects` tells the caller to reset the shared canvas store. */
export function startActionTimeline(planScene, scene, { paused = false } = {}) {
  const steps = Array.isArray(planScene?.steps) ? planScene.steps : [];
  return {
    status: paused ? "paused" : (steps.length ? "playing" : "completed"),
    cursor: 0,
    steps,
    actions: actionIndex(scene),
    elementIds: elementIds(scene),
    clearEffects: true,
  };
}

function completed(session, cursor) {
  return { ...session, cursor, status: "completed", clearEffects: false };
}

function nextSession(session) {
  const cursor = session.cursor + 1;
  return cursor >= session.steps.length
    ? completed(session, cursor)
    : { ...session, cursor, clearEffects: false };
}

function effectFor(action) {
  const elementId = typeof action.elementId === "string" ? action.elementId : "";
  if (action.type === "spotlight") {
    const dimness = Number.isFinite(action.dimOpacity)
      ? action.dimOpacity
      : (Number.isFinite(action.dimness) ? action.dimness : 0.5);
    return { kind: "spotlight", elementId, options: { dimness } };
  }
  if (action.type === "laser") {
    return {
      kind: "laser",
      elementId,
      options: {
        ...(typeof action.color === "string" && action.color ? { color: action.color } : {}),
        ...(Number.isFinite(action.duration) ? { duration: action.duration } : {}),
      },
    };
  }
  return { kind: "play_video", elementId, options: {} };
}

/**
 * Advance exactly one server-planned step. A missing/mismatched/unsupported action is surfaced
 * as `skipped`, never treated as successfully played; callers can show that result to the user.
 */
export function advanceActionTimeline(session) {
  if (!session || session.status !== "playing") {
    return { effect: null, skipped: null, next: session || startActionTimeline() };
  }
  const step = session.steps[session.cursor];
  if (!step) return { effect: null, skipped: null, next: completed(session, session.cursor) };
  const actionId = typeof step.action_id === "string" ? step.action_id : "";
  const action = session.actions.get(actionId);
  if (!action || action.type !== step.type) {
    return {
      effect: null,
      skipped: { actionId, type: step.type || "unknown", reason: "action_not_available" },
      next: nextSession(session),
    };
  }
  if (!EXECUTABLE_TYPES.has(action.type)) {
    return {
      effect: null,
      skipped: { actionId, type: action.type, reason: "client_runtime_unavailable" },
      next: nextSession(session),
    };
  }
  const effect = effectFor(action);
  if (!effect.elementId || !session.elementIds.has(effect.elementId)) {
    return {
      effect: null,
      skipped: { actionId, type: action.type, reason: "element_not_found" },
      next: nextSession(session),
    };
  }
  return { effect, skipped: null, next: nextSession(session) };
}
