/**
 * 编辑器的视图模型。
 *
 * 编辑器是唯一"客户端和服务端各持一份文档"的地方，所以这里的每条规则都对应
 * 一个真实的坏结果：
 *
 * 1. **提交的是命令，不是文档。** 整份回传会把作者没看到的并发修改静默回退。
 * 2. **undo/redo 必须有上限。** 无限保存全量历史会让一个长编辑会话把内存吃光；
 *    超限时丢弃最早的一步（而不是拒绝编辑）。
 * 3. **乐观本地应用必须与服务端一致。** 本地不接受的命令不发出去，否则会出现
 *    "界面改了但服务端没改"的分叉。
 * 4. **type 不可通过 update 改变。** 改类型会同时改变 content 的形状，服务端会拒，
 *    本地也必须在发请求前拦住。
 */

export const SCENE_TYPES = ["slide", "quiz", "interactive", "pbl"];
export const SCENE_TYPE_LABELS = {
  slide: "幻灯片",
  quiz: "测验",
  interactive: "互动",
  pbl: "项目式学习",
};
export const EDITOR_HISTORY_LIMIT = 50;
export const MAX_COMMANDS_PER_REQUEST = 50;

export class EditorCommandError extends Error {
  constructor(code, path, message) {
    super(message);
    this.name = "EditorCommandError";
    this.code = code;
    this.path = path;
  }
}

// ===== 命令构造器 =====

export function sceneCreateCommand(sceneType, { title, afterSceneId } = {}) {
  if (!SCENE_TYPES.includes(sceneType)) {
    throw new EditorCommandError("scene_type_invalid", "sceneType", `不支持的场景类型：${sceneType}`);
  }
  return {
    type: "scene.create",
    sceneType,
    ...(title ? { title } : {}),
    ...(afterSceneId ? { afterSceneId } : {}),
  };
}

export function sceneDeleteCommand(sceneId) {
  return { type: "scene.delete", sceneId };
}

export function sceneDuplicateCommand(sceneId) {
  return { type: "scene.duplicate", sceneId };
}

export function sceneMoveCommand(sceneId, toIndex) {
  return { type: "scene.move", sceneId, toIndex };
}

export function sceneUpdateCommand(sceneId, patch = {}) {
  return { type: "scene.update", sceneId, ...patch };
}

export function slideElementMoveCommand(sceneId, elementId, left, top) {
  if (typeof sceneId !== "string" || !sceneId.trim()) {
    throw new EditorCommandError("scene_id_required", "sceneId", "必须指定场景");
  }
  if (typeof elementId !== "string" || !elementId.trim()) {
    throw new EditorCommandError("element_id_required", "elementId", "必须指定元素");
  }
  if (!Number.isFinite(left) || !Number.isFinite(top)) {
    throw new EditorCommandError("command_field_invalid", "coordinates", "元素坐标必须是有限数字");
  }
  return { type: "slide.element.move", sceneId, elementId, left, top };
}

export function stageUpdateCommand(patch = {}) {
  return { type: "stage.update", ...patch };
}

// ===== 本地镜像（乐观更新） =====

function reindex(scenes) {
  return scenes.map((scene, index) => (scene.order === index ? scene : { ...scene, order: index }));
}

/** 与服务端的 `applyStageCommands` 保持同一语义，但只处理单条命令。 */
export function applyCommandLocally(document, command) {
  if (!document || !Array.isArray(document.scenes)) {
    throw new EditorCommandError("document_invalid", "", "文档没有 scenes 数组");
  }
  const scenes = document.scenes.slice();
  const indexOf = (sceneId) => {
    const found = scenes.findIndex((scene) => scene.id === sceneId);
    if (found === -1) throw new EditorCommandError("scene_not_found", "sceneId", "找不到该场景");
    return found;
  };

  switch (command?.type) {
    case "scene.create": {
      if (!SCENE_TYPES.includes(command.sceneType)) {
        throw new EditorCommandError("scene_type_invalid", "sceneType", "不支持的场景类型");
      }
      if (command.sceneType === "interactive") {
        // 与本地不发明内容的原则一致：服务端也会拒，本地就不该先画出来。
        throw new EditorCommandError(
          "interactive_content_required",
          "content",
          "新建互动场景必须提供 html 或 url",
        );
      }
      const at = command.afterSceneId
        ? indexOf(command.afterSceneId) + 1
        : scenes.length;
      const minimal =
        command.sceneType === "slide"
          ? { type: "slide", canvas: {} }
          : command.sceneType === "quiz"
            ? { type: "quiz", questions: [] }
            : { type: "pbl" };
      const scene = {
        id: command.localId || `local_${Date.now()}_${at}`,
        stageId: document.stage?.id || "",
        title: command.title || "新场景",
        order: at,
        type: command.sceneType,
        content: minimal,
      };
      scenes.splice(at, 0, scene);
      return { ...document, scenes: reindex(scenes) };
    }
    case "scene.delete": {
      scenes.splice(indexOf(command.sceneId), 1);
      return { ...document, scenes: reindex(scenes) };
    }
    case "scene.duplicate": {
      const at = indexOf(command.sceneId);
      const source = scenes[at];
      scenes.splice(at + 1, 0, {
        ...source,
        id: command.localId || `local_${Date.now()}_${at + 1}`,
        title: `${source.title}（副本）`,
        order: at + 1,
        content: JSON.parse(JSON.stringify(source.content ?? {})),
      });
      return { ...document, scenes: reindex(scenes) };
    }
    case "scene.move": {
      const from = indexOf(command.sceneId);
      const to = command.toIndex;
      if (!Number.isInteger(to) || to < 0 || to >= scenes.length) {
        throw new EditorCommandError("scene_move_out_of_range", "toIndex", "目标位置超出范围");
      }
      const [moved] = scenes.splice(from, 1);
      scenes.splice(to, 0, moved);
      return { ...document, scenes: reindex(scenes) };
    }
    case "scene.update": {
      const at = indexOf(command.sceneId);
      const { type, sceneId, ...patch } = command;
      void type;
      void sceneId;
      if (patch.content && patch.content.type !== scenes[at].type) {
        throw new EditorCommandError(
          "content_type_mismatch",
          "content.type",
          "不能改变场景类型，请新建一个场景",
        );
      }
      scenes[at] = { ...scenes[at], ...patch };
      return { ...document, scenes };
    }
    case "slide.element.move": {
      if (!Number.isFinite(command.left) || !Number.isFinite(command.top)) {
        throw new EditorCommandError("command_field_invalid", "coordinates", "元素坐标必须是有限数字");
      }
      const at = indexOf(command.sceneId);
      const scene = scenes[at];
      if (scene.type !== "slide" || scene.content?.type !== "slide") {
        throw new EditorCommandError("slide_element_requires_slide", "sceneId", "只能移动 slide 场景元素");
      }
      const elements = Array.isArray(scene.content.canvas?.elements) ? scene.content.canvas.elements : [];
      const elementAt = elements.findIndex((element) => element?.id === command.elementId);
      if (elementAt === -1) {
        throw new EditorCommandError("element_not_found", "elementId", "找不到该元素");
      }
      const nextElements = elements.slice();
      nextElements[elementAt] = {
        ...nextElements[elementAt],
        left: command.left,
        top: command.top,
      };
      scenes[at] = {
        ...scene,
        content: { ...scene.content, canvas: { ...scene.content.canvas, elements: nextElements } },
      };
      return { ...document, scenes };
    }
    case "stage.update": {
      const { type, ...patch } = command;
      void type;
      return { ...document, stage: { ...document.stage, ...patch } };
    }
    default:
      throw new EditorCommandError("command_type_invalid", "type", "不支持的命令类型");
  }
}

// ===== 有界 undo/redo =====

/**
 * 有界的快照历史。
 *
 * `limit` 之后每推进一步丢弃最早的一步：编辑会话可以很长，而无上限的历史
 * 等于把每一版文档都留在内存里。
 */
export function createEditorHistory({ limit = EDITOR_HISTORY_LIMIT, initial = null } = {}) {
  const past = [];
  let present = initial;
  const future = [];

  return {
    get limit() {
      return limit;
    },
    current: () => present,
    canUndo: () => past.length > 0,
    canRedo: () => future.length > 0,
    depth: () => past.length,
    /** 提交一步新状态；会清空 redo 分支。 */
    push(state) {
      if (present !== null) {
        past.push(present);
        while (past.length > limit) past.shift();
      }
      present = state;
      future.length = 0;
      return present;
    },
    undo() {
      if (past.length === 0) return present;
      future.push(present);
      present = past.pop();
      while (future.length > limit) future.shift();
      return present;
    },
    redo() {
      if (future.length === 0) return present;
      past.push(present);
      while (past.length > limit) past.shift();
      present = future.pop();
      return present;
    },
    reset(state = null) {
      past.length = 0;
      future.length = 0;
      present = state;
      return present;
    },
  };
}

// ===== 读模型 =====

export function normalizeOutline(payload) {
  const scenes = Array.isArray(payload?.scenes) ? payload.scenes : [];
  return {
    stageId: payload?.stage_id || "",
    workspaceId: payload?.workspace_id || "",
    title: payload?.title || "未命名内容",
    revision: Number(payload?.revision) || 0,
    dslVersion: payload?.dsl_version || "",
    scenes: scenes
      .filter((scene) => scene && scene.id)
      .map((scene) => ({
        id: scene.id,
        type: SCENE_TYPES.includes(scene.type) ? scene.type : "unsupported",
        title: scene.title || "未命名场景",
        order: Number(scene.order) || 0,
        actions: Number(scene.actions) || 0,
        updatedAt: scene.updated_at ?? null,
      }))
      .sort((a, b) => a.order - b.order),
  };
}

/**
 * 编辑器失败语义。
 *
 * 服务端把被拒命令的 `code` / `path` 放在 `details` 里，编辑器据此高亮那一行；
 * 丢掉它们只会得到一句"内容未通过校验"，作者不知道该改哪里。
 */
export function describeEditorError(error) {
  const status = error?.response?.status;
  const code = error?.response?.data?.code;
  const detail = error?.response?.data?.message;
  const details = error?.response?.data?.details || {};

  if (code === "OPENMAIC_FUSION_UNAVAILABLE" || status === 503) {
    return { kind: "unavailable", retryable: true, message: detail || "受管服务当前不可用，请稍后重试。" };
  }
  if (code === "OPENMAIC_IDEMPOTENCY_CONFLICT") {
    return { kind: "idempotency", retryable: false, message: detail || "这次提交与上一次的请求内容不一致。" };
  }
  if (code === "OPENMAIC_REVISION_CONFLICT" || status === 409) {
    // 冲突不是失败：重新读取后再重放命令是唯一能继续的动作。
    return { kind: "conflict", retryable: false, message: detail || "内容已被其他操作更新，请重新读取后再提交。" };
  }
  if (code === "OPENMAIC_WORKSPACE_NOT_FOUND" || status === 404) {
    return { kind: "notFound", retryable: false, message: detail || "该内容不存在，可能已被删除。" };
  }
  if (code === "OPENMAIC_DOCUMENT_REJECTED" || status === 422) {
    if (details.service_error === "command_rejected") {
      return {
        kind: "commandRejected",
        retryable: false,
        path: details.path || "",
        message: detail || "这条编辑无法应用。",
      };
    }
    const issues = details.issues;
    const first = Array.isArray(issues) && issues.length ? issues[0] : null;
    return {
      kind: "rejected",
      retryable: false,
      message: first?.message ? `内容未通过校验：${first.message}` : detail || "内容未通过校验，未保存。",
    };
  }
  if (status === 400 || code === "OPENMAIC_INVALID_REQUEST") {
    return { kind: "invalid", retryable: false, message: detail || "请求不合法。" };
  }
  return { kind: "unknown", retryable: true, message: detail || "操作失败，请稍后重试。" };
}

/** 一次提交不得超过服务端的命令上限；超限应在本地就拆成多次提交。 */
export function canSubmitCommands(commands) {
  return Array.isArray(commands) && commands.length > 0 && commands.length <= MAX_COMMANDS_PER_REQUEST;
}

// ===== 命令缓冲（编辑会话） =====

/**
 * 编辑会话的本地缓冲。
 *
 * `preview()` 由「服务端最后一次状态 + 未提交命令」推导，而不是各自维护一份
 * 副本：两份副本一定会分叉，表现为"界面改了但保存后变了回去"。
 *
 * 有界的是**撤销深度**，不是未保存的编辑本身：撤销只保留最近 `limit` 步（多余的
 * 步骤记不住），但已做出的编辑一条都不会被静默丢弃 —— 丢弃用户的编辑比多占一点
 * 内存糟糕得多。未保存编辑另有 `pendingLimit` 兜底，超出时明确报错要求先保存。
 */
export const EDITOR_PENDING_LIMIT = 200;

export function createCommandBuffer({ limit = EDITOR_HISTORY_LIMIT, pendingLimit = EDITOR_PENDING_LIMIT } = {}) {
  let base = null;
  let revision = 0;
  let pending = [];
  let undone = [];

  function recompute() {
    return pending.reduce(
      (document, command) => applyCommandLocally(document, command),
      base,
    );
  }

  return {
    get revision() {
      return revision;
    },
    get pendingCount() {
      return pending.length;
    },
    /** 服务端返回后重设基线：清空缓冲，避免把已保存的命令再提交一次。 */
    setBase(document, nextRevision) {
      base = document;
      revision = Number(nextRevision) || 0;
      pending = [];
      undone = [];
    },
    /** 服务端的最新 revision（并发冲突后重新读取时更新）。 */
    setRevision(nextRevision) {
      revision = Number(nextRevision) || revision;
    },
    preview: recompute,
    isDirty: () => pending.length > 0,
    /** 只能撤销最近 `limit` 步：更早的步骤不再保留。 */
    canUndo: () => pending.length > 0 && undone.length < limit,
    canRedo: () => undone.length > 0,
    run(command) {
      if (pending.length >= pendingLimit) {
        throw new EditorCommandError(
          "pending_limit_reached",
          "",
          `未保存的编辑过多（>${pendingLimit}），请先保存`,
        );
      }
      // 先本地应用：本地不接受（例如改类型）的命令绝不发出去。
      applyCommandLocally(recompute(), command);
      pending.push(command);
      undone = [];
      return recompute();
    },
    undo() {
      if (!this.canUndo()) return recompute();
      undone.push(pending.pop());
      while (undone.length > limit) undone.shift();
      return recompute();
    },
    redo() {
      if (undone.length === 0) return recompute();
      pending.push(undone.pop());
      return recompute();
    },
    /** 按服务端上限切分，供一次保存分批提交。不丢任何一条待保存命令。 */
    takeBatches(max = MAX_COMMANDS_PER_REQUEST) {
      const batches = [];
      for (let index = 0; index < pending.length; index += max) {
        batches.push(pending.slice(index, index + max));
      }
      return batches;
    },
    snapshot: () => pending.slice(),
  };
}
