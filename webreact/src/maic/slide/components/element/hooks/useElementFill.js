/**
 * 逐字移植自参考
 * `components/slide-renderer/components/element/hooks/useElementFill.ts`。
 * 只做两处机械改写：去掉 TypeScript 类型、`@magicclass/dsl` 类型导入。
 */
import { useMemo } from 'react';

/**
 * Calculate element fill style
 * Returns pattern/gradient URL or solid color fill
 * @param element Shape element
 * @param source Source identifier for pattern/gradient IDs
 */
export function useElementFill(element, source) {
  const fill = useMemo(() => {
    if (element.pattern) return `url(#${source}-pattern-${element.id})`;
    if (element.gradient) return `url(#${source}-gradient-${element.id})`;
    return element.fill || 'none';
  }, [element.pattern, element.gradient, element.fill, element.id, source]);

  return {
    fill,
  };
}
