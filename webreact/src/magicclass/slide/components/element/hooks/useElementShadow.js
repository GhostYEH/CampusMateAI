/**
 * 逐字移植自参考
 * `components/slide-renderer/components/element/hooks/useElementShadow.ts`。
 * 只去掉 TypeScript 类型与 `@magicclass/dsl` 类型导入。
 */
import { useMemo } from 'react';

/**
 * Calculate element shadow style
 * Converts shadow object to CSS box-shadow string
 * @param shadow Shadow configuration
 */
export function useElementShadow(shadow) {
  const shadowStyle = useMemo(() => {
    if (shadow) {
      const { h, v, blur, color } = shadow;
      return `${h}px ${v}px ${blur}px ${color}`;
    }
    return '';
  }, [shadow]);

  return {
    shadowStyle,
  };
}
