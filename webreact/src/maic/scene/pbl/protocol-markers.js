/**
 * 移植自参考项目 `components/scene-renderers/pbl/v2/protocol-markers.ts`。
 * 逐字复制（该文件没有 TypeScript 类型）。
 */
export const TASK_DIVIDER_PREFIX = '[TASK_DIVIDER]';
export const MILESTONE_DIVIDER_PREFIX = '[MILESTONE_DIVIDER]';

const DIVIDER_MARKER_PATTERN = /[^\S\r\n]*(?:\[TASK_DIVIDER\]|\[MILESTONE_DIVIDER\])[^\r\n]*/g;

export function stripEmbeddedDividerMarkers(text) {
  return text.replace(DIVIDER_MARKER_PATTERN, '').trim();
}

export function isStandaloneDividerMessage(content) {
  return content.startsWith(TASK_DIVIDER_PREFIX) || content.startsWith(MILESTONE_DIVIDER_PREFIX);
}
