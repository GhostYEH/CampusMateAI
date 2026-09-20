/**
 * 移植自参考项目 `lib/pbl/v2/readers.ts`。
 * Read a possibly malformed persisted leaf as trimmed text.
 */
export function trimmedPBLText(value) {
  return typeof value === 'string' ? value.trim() : '';
}
