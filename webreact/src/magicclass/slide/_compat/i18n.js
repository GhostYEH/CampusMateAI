/**
 * 移植补充：`useI18n` 的等价层 + 媒体文案注入点。
 *
 * 参考项目用 `@/lib/hooks/use-i18n`（i18next）。任务明确禁止引入 i18next，所以
 * 这里给被移植组件提供一个同形状的 `t(key)`：默认返回中文字面量，`mediaStrings`
 * 可以覆盖任意条目（沿用参考项目 `settings.mediaGenerationDisabled` /
 * `settings.mediaRetry` 两个 key）。
 */
import { createContext, useContext } from 'react';

export const DEFAULT_MEDIA_STRINGS = {
  'settings.mediaGenerationDisabled': '素材生成已关闭',
  'settings.mediaRetry': '重试',
};

const MediaStringsContext = createContext(null);

export const MediaStringsProvider = MediaStringsContext.Provider;

function interpolate(template, options) {
  if (!options || typeof template !== 'string') return template;
  return template.replace(/\{\{\s*([\w.]+)\s*\}\}/g, (match, key) => {
    const value = options[key];
    return value === undefined || value === null ? match : String(value);
  });
}

export function createTranslator(overrides) {
  const dictionary = { ...DEFAULT_MEDIA_STRINGS, ...(overrides || {}) };
  return (key, options) => {
    const template = dictionary[key];
    if (template === undefined) return key;
    return interpolate(template, options);
  };
}

export function useI18n() {
  const overrides = useContext(MediaStringsContext);
  const t = createTranslator(overrides);
  return { t };
}

/**
 * 参考项目 `lib/logger.ts#createLogger` 的最小替代。
 * 保留同样的四个级别方法，方便被移植文件里的调用点原样保留。
 */
export function createLogger(namespace) {
  return {
    debug: (...args) => console.debug(`[${namespace}]`, ...args),
    info: (...args) => console.info(`[${namespace}]`, ...args),
    warn: (...args) => console.warn(`[${namespace}]`, ...args),
    error: (...args) => console.error(`[${namespace}]`, ...args),
  };
}
