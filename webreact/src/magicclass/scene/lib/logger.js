/**
 * 移植自参考项目 `lib/logger.ts`。
 *
 * 参考项目的 logger 是一层薄薄的 console 包装（带 scope 前缀），唯一的
 * 机械改写是去掉 TypeScript 类型。
 */
export function createLogger(scope) {
  const prefix = `[${scope}]`;
  return {
    debug: (...args) => console.debug(prefix, ...args),
    info: (...args) => console.info(prefix, ...args),
    warn: (...args) => console.warn(prefix, ...args),
    error: (...args) => console.error(prefix, ...args),
  };
}
