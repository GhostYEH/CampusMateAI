/**
 * `.maic.zip` 的视图模型。
 *
 * 档案这一面在界面上有两件事最容易做错，所以在这里定死：
 *
 * 1. **文件名来自服务端。** 服务端按学生填的标题生成了下载名并放进
 *    `Content-Disposition`（中文走 RFC 5987 的 `filename*`），前端只负责解析，
 *    不自己用标题拼一个——拼出来的名字会在下次服务端改规则时静默分叉。
 * 2. **导入前先自查。** 超过上限或明显不是 zip 的文件在本地就被拦下，不去换一个
 *    必然失败的 400/422。
 */

/** 与服务端一致：网关与受管服务各拦一次。 */
export const MAX_ARCHIVE_BYTES = Math.floor(2.5 * 1024 * 1024);
export const ARCHIVE_SUFFIX = ".maic.zip";
const FALLBACK_FILENAME = "学习内容.maic.zip";

/**
 * 从 `Content-Disposition` 里取出下载名。
 *
 * 优先 `filename*=UTF-8''…`（RFC 5987），它是唯一能承载中文的那一个；
 * 只有它缺失时才退回 `filename="…"`。两者都没有时给一个确定的名字，
 * 而不是把整个头当作文件名。
 */
export function filenameFromContentDisposition(disposition) {
  const header = String(disposition ?? "");
  if (!header) return FALLBACK_FILENAME;

  const extended = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(header);
  if (extended) {
    try {
      const decoded = decodeURIComponent(extended[1].trim());
      if (decoded) return sanitizeFilename(decoded);
    } catch {
      // 百分号编码坏了就继续看基本形式，绝不把坏字节当文件名。
    }
  }

  const basic = /filename\s*=\s*"([^"]*)"/i.exec(header) || /filename\s*=\s*([^;]+)/i.exec(header);
  if (basic) {
    const value = basic[1].trim();
    if (value) return sanitizeFilename(value);
  }
  return FALLBACK_FILENAME;
}

/** 一个文件名就是名字，永远不是路径。 */
export function sanitizeFilename(value) {
  const text = String(value ?? "")
    .replace(/[\u0000-\u001f\u007f]/g, "")
    .replace(/[\\/]/g, " ")
    .trim();
  if (!text) return FALLBACK_FILENAME;
  return text.length > 120 ? text.slice(0, 120) : text;
}

/** 导入前的本地自查。返回 `null` 表示可以提交。 */
export function validateImportCandidate(file) {
  if (!file) return "请选择一个 .maic.zip 档案。";
  const name = String(file.name ?? "").trim();
  if (!name) return "文件名不能为空。";
  if (name.includes("/") || name.includes("\\")) return "文件名不能包含路径分隔符。";
  if (!/\.zip$/i.test(name)) return "请选择 .maic.zip 档案。";
  const size = Number(file.size);
  if (!Number.isFinite(size) || size < 0) return "无法读取文件大小，请重新选择。";
  if (size === 0) return "档案是空的。";
  if (size > MAX_ARCHIVE_BYTES) {
    return `档案不能超过 ${Math.round(MAX_ARCHIVE_BYTES / 1024 / 1024 * 10) / 10} MB。`;
  }
  return null;
}

/** 导入成功后服务端返回的那份 stage。 */
export function normalizeImportedStage(payload) {
  const stage = payload?.stage ?? payload;
  if (!stage || !stage.id) return null;
  return {
    id: stage.id,
    workspaceId: stage.workspace_id,
    courseId: stage.course_id,
    title: stage.title || "导入的学习内容",
    revision: Number(stage.revision) || 0,
    dslVersion: stage.dsl_version || "",
    updatedAt: stage.updated_at || stage.created_at || "",
    migrated: Boolean(payload?.migrated),
    sourceWorkspaceName: payload?.source_workspace_name || "",
  };
}

/**
 * 失败翻译。与工作台共用语义，并多一类：422 是"这个档案本身不合格"，
 * 重试没有意义——服务端把具体原因放在 `details.service_message` 里，
 * 那是唯一能告诉学生"改什么"的东西。
 */
export function describeArchiveError(error) {
  const status = error?.response?.status;
  const code = error?.response?.data?.code;
  const detail = error?.response?.data?.message;
  const serviceMessage = error?.response?.data?.details?.service_message;

  if (code === "MAGICCLASS_FUSION_UNAVAILABLE" || status === 503) {
    return { kind: "unavailable", retryable: true, message: detail || "受管服务当前不可用，请稍后重试。" };
  }
  if (code === "MAGICCLASS_DOCUMENT_REJECTED" || status === 422) {
    return { kind: "rejected", retryable: false, message: serviceMessage || detail || "这个档案未通过校验。" };
  }
  if (code === "MAGICCLASS_IDEMPOTENCY_CONFLICT") {
    return { kind: "idempotency", retryable: false, message: detail || "这次提交与上一次的内容不一致，请重新提交。" };
  }
  if (code === "MAGICCLASS_REVISION_CONFLICT" || status === 409) {
    return { kind: "conflict", retryable: false, message: detail || "内容已被其他操作更新，请重新读取。" };
  }
  if (code === "MAGICCLASS_WORKSPACE_NOT_FOUND" || status === 404) {
    return { kind: "notFound", retryable: false, message: detail || "目标工作台不存在，可能已被删除。" };
  }
  if (status === 400 || code === "MAGICCLASS_INVALID_REQUEST") {
    return { kind: "invalid", retryable: false, message: detail || "请求不合法。" };
  }
  return { kind: "unknown", retryable: true, message: detail || "操作失败，请稍后重试。" };
}
