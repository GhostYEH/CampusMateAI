/**
 * 课程资料的视图模型。
 *
 * 资料这一面最容易在界面上撒谎，所以三件事在这里定死：
 *
 * 1. **解析不了就说解析不了。** `unsupported` 的条目没有任何正文，界面必须显示
 *    "无正文"并说明原因，绝不能渲染一个空的正文区域让人以为文件是空的。
 * 2. **正文只在单份读取时出现。** 列表里的 `text_chars` 是数字；把 `text` 从列表
 *    映射进来会让一次列表的开销随语料规模增长。
 * 3. **上传前先自查。** 超过上限或文件名带路径分隔符的文件在本地就被拦下，
 *    不去换一个必然失败的 422/400。
 */

export const MATERIALS_PAGE_LIMIT = 20;
/** 与服务端 `MAX_MATERIAL_BYTES` 一致：本地先拦，网关再拦一次。 */
export const MAX_UPLOAD_BYTES = 2 * 1024 * 1024;
export const MAX_FILENAME_LENGTH = 255;
export const MAX_MATERIAL_IDS = 50;

const STATUS_COPY = {
  extracted: { tone: "ready", label: "已解析", hint: "" },
  unsupported: {
    tone: "muted",
    label: "无正文",
    hint: "该格式暂不支持解析，资料会保留，但暂时不能被引用为正文。",
  },
  empty: { tone: "muted", label: "空文件", hint: "文件里没有可读取的内容。" },
};

const UNKNOWN_STATUS = {
  tone: "muted",
  label: "状态未知",
  hint: "服务端返回了未识别的解析状态，界面不猜测它的含义。",
};

/** 解析状态 -> 界面文案。未知状态不猜测，直接说未知。 */
export function describeExtractionStatus(status) {
  return STATUS_COPY[status] || UNKNOWN_STATUS;
}

function summarize(item) {
  return {
    id: item.id,
    courseId: item.course_id,
    filename: item.filename || "未命名资料",
    mediaType: item.media_type || "application/octet-stream",
    byteSize: Number(item.byte_size) || 0,
    sha256: item.sha256 || "",
    extractionStatus: item.extraction_status || "unsupported",
    textChars: Number(item.text_chars) || 0,
    revision: Number(item.revision) || 0,
    createdAt: item.created_at || "",
    updatedAt: item.updated_at || item.created_at || "",
    deduplicated: Boolean(item.deduplicated),
  };
}

export function normalizeMaterialList(payload) {
  const items = Array.isArray(payload) ? payload : payload?.items;
  return (items || []).filter((item) => item && item.id).map(summarize);
}

/**
 * 单份资料。
 *
 * `text` 只在服务端真的给了它、且状态说明"确实提取过"的时候才映射：否则一个
 * 状态为 `unsupported` 的行会带着正文出现在界面上，正好是这一层要防的事。
 */
export function normalizeMaterialDetail(payload) {
  if (!payload || !payload.id) return null;
  const summary = summarize(payload);
  const text = summary.extractionStatus === "extracted" ? String(payload.text ?? "") : "";
  return { ...summary, text };
}

export function normalizeMaterialResolution(payload) {
  const resolved = (payload?.resolved || [])
    .filter((item) => item && item.id)
    .map((item) => ({
      id: item.id,
      filename: item.filename || "未命名资料",
      mediaType: item.media_type || "application/octet-stream",
      extractionStatus: item.extraction_status || "unsupported",
      textChars: Number(item.text_chars) || 0,
      updatedAt: item.updated_at || "",
    }));
  const unresolved = (payload?.unresolved || [])
    .filter((item) => typeof item === "string" && item)
    .map(String);
  return { resolved, unresolved };
}

/** 上传前的本地自查。返回 `null` 表示可以提交，否则返回拒绝原因。 */
export function validateUploadCandidate(file) {
  if (!file) return "请选择一个文件。";
  const name = String(file.name ?? "").trim();
  if (!name) return "文件名不能为空。";
  if (name.length > MAX_FILENAME_LENGTH) return `文件名不能超过 ${MAX_FILENAME_LENGTH} 个字符。`;
  if (name.includes("/") || name.includes("\\")) return "文件名不能包含路径分隔符。";
  const size = Number(file.size);
  if (!Number.isFinite(size) || size < 0) return "无法读取文件大小，请重新选择。";
  if (size > MAX_UPLOAD_BYTES) {
    return `文件不能超过 ${formatBytes(MAX_UPLOAD_BYTES)}，当前 ${formatBytes(size)}。`;
  }
  return null;
}

/** 只有服务器确认过的资料才会进入可引用集合。 */
export function referenceIds(materials = []) {
  return materials
    .filter((item) => item && item.id && item.extractionStatus === "extracted")
    .slice(0, MAX_MATERIAL_IDS)
    .map((item) => item.id);
}

export function formatBytes(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes < 0) return "未知大小";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** 上传成功后把新资料放进列表：同 id 视为同一条，避免重复行。 */
export function upsertMaterial(materials, material) {
  if (!material || !material.id) return materials;
  const others = materials.filter((item) => item.id !== material.id);
  return [material, ...others];
}

/**
 * 失败翻译。与工作台/发现共用语义：503 可重试，409 先重新读取，400 是输入问题。
 * 资料的 422 只可能是"这次文件本身不合格"，重试没有意义。
 */
export function describeMaterialError(error) {
  const status = error?.response?.status;
  const code = error?.response?.data?.code;
  const detail = error?.response?.data?.message;

  if (code === "OPENMAIC_FUSION_UNAVAILABLE" || status === 503) {
    return { kind: "unavailable", retryable: true, message: detail || "受管服务当前不可用，请稍后重试。" };
  }
  if (code === "OPENMAIC_DOCUMENT_REJECTED" || status === 422) {
    return { kind: "rejected", retryable: false, message: detail || "该文件未通过校验，请更换后重试。" };
  }
  if (code === "OPENMAIC_IDEMPOTENCY_CONFLICT") {
    return { kind: "idempotency", retryable: false, message: detail || "这次提交与上一次的请求内容不一致，请重新提交。" };
  }
  if (code === "OPENMAIC_REVISION_CONFLICT" || status === 409) {
    return { kind: "conflict", retryable: false, message: detail || "内容已被其他操作更新，请重新读取后再提交。" };
  }
  if (code === "OPENMAIC_WORKSPACE_NOT_FOUND" || status === 404) {
    return { kind: "notFound", retryable: false, message: detail || "该资料不存在，可能已被删除。" };
  }
  if (status === 400 || code === "OPENMAIC_INVALID_REQUEST") {
    return { kind: "invalid", retryable: false, message: detail || "请求不合法。" };
  }
  return { kind: "unknown", retryable: true, message: detail || "操作失败，请稍后重试。" };
}

/** 游标原样带回，前端不解析它。 */
export function nextCursorOf(payload) {
  const cursor = payload?.next_cursor;
  return typeof cursor === "string" && cursor ? cursor : null;
}
