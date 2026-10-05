/**
 * 移植自参考项目 `lib/interactive/element-reference-policy.ts`。
 * 仅擦除 TypeScript 类型（`as const` 与 `Set<string>` 泛型）。
 */

/** Tags that cannot be selected as static Interactive courseware evidence. */
export const INTERACTIVE_REFERENCE_EXCLUDED_TAG_NAMES = [
  'html',
  'head',
  'body',
  'script',
  'style',
  'link',
  'meta',
  'noscript',
  'template',
  'iframe',
  'canvas',
  'noembed',
  'noframes',
  'plaintext',
  'xmp',
];

const INTERACTIVE_REFERENCE_EXCLUDED_TAG_SET = new Set(INTERACTIVE_REFERENCE_EXCLUDED_TAG_NAMES);

export function isInteractiveReferenceExcludedTag(tagName) {
  return INTERACTIVE_REFERENCE_EXCLUDED_TAG_SET.has(String(tagName).toLowerCase());
}
