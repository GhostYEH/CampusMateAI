/**
 * 讲解音频的视图模型。
 *
 * 讲解音频最容易出现的两种"看起来坏了"的情况，都在这层挡掉：
 *
 * 1. **把失败说成"没有内容"。** "这一页确实没有可讲的文字"和"合成失败了，可以重试"
 *    是两件事：前者不该再点，后者应该再点。合并成一句"暂无音频"，学生就无从判断。
 * 2. **把 Provider 未配置说成网络错误。** 未配置是部署问题（重试无用），服务不可达
 *    是瞬时问题（可以重试）。两种都要有自己的说法。
 */

/**
 * 从服务端返回的 `error_code` / HTTP 状态翻译成可行动的中文。
 *
 * 与圆桌的 `describeDiscussionFailure` 同构：先看稳定错误码，再看状态码，最后
 * 才回落到原始信息——但**绝不吞掉**，未知原因也要说清是哪一类未知。
 */
const FAILURE_COPY = {
  provider_unavailable: "本部署还没有配置语音合成，暂时无法生成讲解音频。",
  provider_timeout: "语音合成超时了，可以再试一次。",
  provider_rejected: "语音合成服务拒绝了这次请求，请稍后重试。",
  provider_request_failed: "连不上语音合成服务，请检查网络后重试。",
  provider_invalid_response: "语音合成服务返回了无法识别的结果，请稍后重试。",
  internal_error: "语音合成过程中出错了，可以重试。",
  OPENMAIC_FUSION_UNAVAILABLE: "暂时连不上受管 OpenMAIC 服务，请稍后重试。",
  OPENMAIC_INVALID_REQUEST: "这次请求不合法，请重新打开这一页再试。",
};

export function describeNarrationFailure(error) {
  const status = error?.response?.status;
  const code = error?.response?.data?.code || error?.code;
  const detail = error?.response?.data?.detail || error?.response?.data?.message;

  if (code && FAILURE_COPY[code]) return FAILURE_COPY[code];
  if (status === 503) return FAILURE_COPY.provider_unavailable;
  if (status === 401) return "登录已过期，请重新登录后再试。";
  if (status === 403) return "没有权限访问这一页的讲解音频。";
  if (status === 404) return "这一页已经不存在了，请返回重新进入课堂。";
  if (status === 400) return FAILURE_COPY.OPENMAIC_INVALID_REQUEST;
  if (detail) return String(detail);
  if (error?.message) return String(error.message);
  return "讲解音频没能生成，请稍后重试。";
}

/**
 * 面板文案。五态互斥——`none`（没内容可讲）与 `failed`（出错了）必须分开，
 * 因为它们的下一步动作不同。
 */
export function narrationLabel({ state, truncated = false } = {}) {
  switch (state) {
    case "checking": return "正在检查这一页的讲解…";
    case "generating": return "正在生成这一页的讲解，请稍候…";
    case "ready": return truncated ? "讲解音频已生成（因原文较长已截断）。" : "讲解音频已生成。";
    case "none": return "这一页没有可讲解的文字。";
    case "error": return "讲解音频暂时不可用。";
    default: return "";
  }
}

/**
 * 是否展示"生成讲解"按钮。
 *
 * **只有失败才给重试入口。** `none`（这一页没有可讲解的文字）不给——再点一次
 * 只会得到同样的答案，一个点不出结果的按钮比没有按钮更糟。
 * `ready` / `generating` 也不给，避免诱导重复提交（服务端虽能去重，界面不该鼓励）。
 */
export function canGenerateNarration({ state } = {}) {
  return state === "error";
}
