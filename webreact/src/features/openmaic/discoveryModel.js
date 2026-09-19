/**
 * 文件夹与站内搜索的视图模型。
 *
 * 三件事在界面上最容易表现为"看起来能用其实不能用"，所以在这里定死：
 *
 * 1. **空关键词不是"搜索全部"。** `isSearchableQuery` 为假时界面不发请求，
 *    否则用户清空输入框会得到整个课程的内容。
 * 2. **深链由服务端给出。** `path` 原样使用，前端不自己拼 `/courses/...`，
 *    否则服务端改口径时前端会静默走到别处。
 * 3. **文件夹树必须能处理坏数据。** `parent_id` 指向一个不存在或已删除的文件夹
 *    （例如删除父文件夹的瞬间）时，该文件夹上浮到根层而不是整棵树消失。
 */

export const DISCOVERY_PAGE_LIMIT = 20;
export const MAX_SEARCH_QUERY_LENGTH = 200;

export function normalizeFolderList(payload) {
  const items = Array.isArray(payload) ? payload : payload?.items;
  return (items || [])
    .filter((item) => item && item.id)
    .map((item) => ({
      id: item.id,
      courseId: item.course_id,
      parentId: item.parent_id || null,
      name: item.name || "未命名文件夹",
      revision: Number(item.revision) || 0,
      workspaceCount: Number(item.workspace_count) || 0,
      updatedAt: item.updated_at || item.created_at || "",
    }));
}

/**
 * 把平铺列表变成树。
 *
 * 缺失父节点的条目上浮到根层：级联删除期间的一次读取会短暂出现这种数据，
 * 让它整棵树消失比让它暂时出现在根层糟糕得多。
 */
export function buildFolderTree(folders = []) {
  const byId = new Map(folders.map((folder) => [String(folder.id), folder]));
  const children = new Map();
  const roots = [];
  folders.forEach((folder) => {
    const parentId = folder.parentId ? String(folder.parentId) : null;
    const hasParent = parentId && byId.has(parentId) && parentId !== String(folder.id);
    if (!hasParent) {
      roots.push(folder);
      return;
    }
    if (!children.has(parentId)) children.set(parentId, []);
    children.get(parentId).push(folder);
  });
  const sort = (list) => list.slice().sort((a, b) => a.name.localeCompare(b.name, "zh-Hans-CN"));
  return { roots: sort(roots), childrenOf: (id) => sort(children.get(String(id)) || []) };
}

/** 文件夹名称：去掉首尾空白并限长，与服务端字段约束一致。 */
export function normalizeFolderName(value) {
  const name = String(value ?? "").trim();
  if (!name || name.length > 120) return null;
  return name;
}

export function isSearchableQuery(value) {
  const query = String(value ?? "").trim();
  return query.length > 0 && query.length <= MAX_SEARCH_QUERY_LENGTH;
}

export function normalizeSearchResults(payload) {
  const items = Array.isArray(payload) ? payload : payload?.items;
  return (items || [])
    .filter((item) => item && item.workspace_id && (item.kind === "workspace" || item.kind === "stage"))
    .map((item) => ({
      kind: item.kind,
      workspaceId: item.workspace_id,
      stageId: item.stage_id || null,
      title: item.title || "未命名内容",
      snippet: item.snippet || "",
      folderId: item.folder_id || null,
      updatedAt: item.updated_at || "",
      // 深链是服务端产物；缺失时宁可回到课程页，也不在前端拼一条可能过期的路径。
      href: item.path || null,
    }));
}

/** 命中项的稳定 key：同一个工作台和它的 stage 会同时出现。 */
export function searchHitKey(hit) {
  return `${hit.kind}:${hit.stageId || hit.workspaceId}`;
}

/**
 * 把发现功能的失败翻译成界面能据以行动的种类。
 *
 * 与工作台共用一套语义：503 可重试，409 必须先重新读取，400 是输入问题。
 * 搜索没有并发写入，所以这里不会出现冲突分支。
 */
export function describeDiscoveryError(error) {
  const status = error?.response?.status;
  const code = error?.response?.data?.code;
  const detail = error?.response?.data?.message;

  if (code === "OPENMAIC_FUSION_UNAVAILABLE" || status === 503) {
    return { kind: "unavailable", retryable: true, message: detail || "受管服务当前不可用，请稍后重试。" };
  }
  // 幂等键冲突必须先于通用 409 判断：两者都是 409，但含义不同——前者要换键或换
  // 内容，后者要先重新读取。归错类会让界面给出错误的下一步。
  if (code === "OPENMAIC_IDEMPOTENCY_CONFLICT") {
    return { kind: "idempotency", retryable: false, message: detail || "这次提交与上一次的请求内容不一致，请重新提交。" };
  }
  if (code === "OPENMAIC_REVISION_CONFLICT" || status === 409) {
    return { kind: "conflict", retryable: false, message: detail || "内容已被其他操作更新，请重新读取后再提交。" };
  }
  if (code === "OPENMAIC_WORKSPACE_NOT_FOUND" || status === 404) {
    return { kind: "notFound", retryable: false, message: detail || "该内容不存在，可能已被删除。" };
  }
  if (status === 400 || code === "OPENMAIC_INVALID_REQUEST") {
    return { kind: "invalid", retryable: false, message: detail || "请求不合法。" };
  }
  return { kind: "unknown", retryable: true, message: detail || "操作失败，请稍后重试。" };
}

/** 游标：服务端给什么就带什么回去，前端不解析它。 */
export function nextCursorOf(payload) {
  const cursor = payload?.next_cursor;
  return typeof cursor === "string" && cursor ? cursor : null;
}
