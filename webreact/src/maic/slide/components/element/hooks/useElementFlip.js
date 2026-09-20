/**
 * 逐字移植自参考
 * `components/slide-renderer/components/element/hooks/useElementFlip.ts`。
 * 只去掉 TypeScript 类型。
 */
import { useMemo } from 'react';

/**
 * Calculate element flip transform style
 * Handles horizontal and/or vertical flip
 * @param flipH Flip horizontally
 * @param flipV Flip vertically
 */
export function useElementFlip(flipH, flipV) {
  const flipStyle = useMemo(() => {
    let style = '';

    if (flipH && flipV) style = 'rotateX(180deg) rotateY(180deg)';
    else if (flipV) style = 'rotateX(180deg)';
    else if (flipH) style = 'rotateY(180deg)';

    return style;
  }, [flipH, flipV]);

  return {
    flipStyle,
  };
}
