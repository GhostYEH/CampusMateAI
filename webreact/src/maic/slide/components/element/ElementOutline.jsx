/**
 * 逐字移植自参考 `components/slide-renderer/components/element/ElementOutline.tsx`。
 * 只做两处机械改写：去掉 `'use client'` 与 TypeScript 类型。
 */
import { useElementOutline } from './hooks/useElementOutline.js';

/**
 * Element outline (border) component
 * Renders an SVG outline around an element based on outline configuration
 */
export function ElementOutline({ width, height, outline }) {
  const { outlineWidth, outlineColor, strokeDashArray } = useElementOutline(outline);

  if (!outline) return null;

  return (
    <svg
      className="element-outline absolute top-0 left-0 overflow-visible"
      width={width}
      height={height}
    >
      <path
        vectorEffect="non-scaling-stroke"
        strokeLinecap="butt"
        strokeMiterlimit="8"
        fill="transparent"
        d={`M0,0 L${width},0 L${width},${height} L0,${height} Z`}
        stroke={outlineColor}
        strokeWidth={outlineWidth}
        strokeDasharray={strokeDashArray}
      />
    </svg>
  );
}
