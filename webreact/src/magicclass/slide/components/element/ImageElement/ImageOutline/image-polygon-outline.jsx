/**
 * 逐字移植自参考
 * `components/slide-renderer/components/element/ImageElement/ImageOutline/image-polygon-outline.tsx`。
 * 只去掉 `'use client'` 与 TypeScript 类型。
 */
import { useElementOutline } from '../../hooks/useElementOutline.js';

/**
 * Polygon outline for image element
 */
export function ImagePolygonOutline({ width, height, createPath, outline }) {
  const { outlineWidth, outlineColor, strokeDashArray } = useElementOutline(outline);

  if (!outline) return null;

  return (
    <svg className="absolute top-0 left-0 z-[2] overflow-visible" width={width} height={height}>
      <path
        vectorEffect="non-scaling-stroke"
        strokeLinecap="butt"
        strokeMiterlimit="8"
        fill="transparent"
        d={createPath(width, height)}
        stroke={outlineColor}
        strokeWidth={outlineWidth}
        strokeDasharray={strokeDashArray}
      />
    </svg>
  );
}
