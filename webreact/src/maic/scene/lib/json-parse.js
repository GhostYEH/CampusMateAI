/**
 * 近似替换：参考项目 `@magicclass/generation` 导出的 `parseJsonResponse`
 * （实现位于 `packages/@magicclass/generation/src/json-repair.ts`），它依赖 npm 包
 * `jsonrepair` 修复被截断 / 含注释 / 含尾逗号的 LLM JSON 输出。
 *
 * 目标项目既没有 `jsonrepair`，也没有那个 workspace 包，所以这里保留**同一套调用
 * 契约**（`parseJsonResponse(text, options) -> T | null`，失败返回 null），但修复
 * 能力收窄为：
 *   1. 原文直接 `JSON.parse`
 *   2. 剥掉 ```json / ``` 围栏后重试
 *   3. 取最后一个平衡的 `{...}` / `[...]` 子串重试
 *   4. 去掉对象 / 数组尾逗号后重试
 *
 * 对"围栏 JSON、裸 JSON、散文 + JSON 尾巴"这三种评测器实际会产出的形态，
 * 结果与上游一致；只有真正被截断或严重畸形的 JSON 会比上游更早失败——此时返回
 * null，调用方（eval-tail-parser）本就把 null 当作"没有结构化尾巴"处理。
 */

function stripFences(text) {
  const fenced = /```(?:json)?\s*([\s\S]*?)```/i.exec(text);
  return fenced ? fenced[1].trim() : text;
}

function lastBalancedRange(text, open, close) {
  const lastClose = text.lastIndexOf(close);
  if (lastClose < 0) return null;
  let depth = 0;
  for (let i = lastClose; i >= 0; i -= 1) {
    const ch = text[i];
    if (ch === close) depth += 1;
    else if (ch === open) {
      depth -= 1;
      if (depth === 0) return text.slice(i, lastClose + 1);
    }
  }
  return null;
}

function removeTrailingCommas(text) {
  return text.replace(/,\s*([}\]])/g, '$1');
}

function tryParse(text) {
  if (typeof text !== 'string') return undefined;
  const candidates = [];
  const trimmed = text.trim();
  if (!trimmed) return undefined;
  candidates.push(trimmed);
  const unfenced = stripFences(trimmed);
  if (unfenced !== trimmed) candidates.push(unfenced);
  for (const source of [trimmed, unfenced]) {
    const objectRange = lastBalancedRange(source, '{', '}');
    if (objectRange) candidates.push(objectRange);
    const arrayRange = lastBalancedRange(source, '[', ']');
    if (arrayRange) candidates.push(arrayRange);
  }
  // De-duplicate while preserving priority order.
  const seen = new Set();
  for (const candidate of candidates) {
    if (seen.has(candidate)) continue;
    seen.add(candidate);
    for (const attempt of [candidate, removeTrailingCommas(candidate)]) {
      try {
        return JSON.parse(attempt);
      } catch {
        // try the next candidate
      }
    }
  }
  return undefined;
}

export function parseJsonResponse(response, options = {}) {
  if (typeof response !== 'string') return null;
  const parsed = tryParse(response);
  if (parsed === undefined || parsed === null) {
    if (typeof options.onError === 'function') options.onError(response);
    return null;
  }
  return parsed;
}

export function tryParseJson(jsonStr, options = {}) {
  return parseJsonResponse(jsonStr, options);
}
