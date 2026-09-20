/**
 * 移植补充：富文本行高判定。
 *
 * 逐字移植自参考 `packages/@openmaic/renderer/src/utils/richText.ts`。
 */
const HTML_MARKUP_PATTERN = /<\/?[a-z][^>]*>|<![^>]*>/i;

export function preservesPlainTextLineBreaks(content) {
  return !HTML_MARKUP_PATTERN.test(content);
}
