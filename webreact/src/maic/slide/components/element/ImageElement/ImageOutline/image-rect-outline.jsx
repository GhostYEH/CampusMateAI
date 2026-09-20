/**
 * 逐字移植自参考
 * `components/slide-renderer/components/element/ImageElement/ImageOutline/image-rect-outline.tsx`。
 * 只去掉 `'use client'` 与 TypeScript 类型。
 */
import { useElementOutline } from '../../hooks/useElementOutline.js';

/**
 * Rectangle outline for image element
 */
export function ImageRectOutline({ width, height, outline, radius = '0' }) {
  const { outlineWidth, outlineColor, strokeDashArray } = useElementOutline(outline);

  if (!outline) return null;

  return (
    <svg className="absolute top-0 left-0 z-[2] overflow-visible" width={width} height={height}>
      <rect
        vectorEffect="non-scaling-stroke"
        strokeLinecap="butt"
        strokeMiterlimit="8"
        fill="transparent"
        rx={radius}
        ry={radius}
        width={width}
        height={height}
        stroke={outlineColor}
        strokeWidth={outlineWidth}
        strokeDasharray={strokeDashArray}
      />
    </svg>
  );
}
