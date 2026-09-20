/**
 * 逐字移植自参考
 * `components/slide-renderer/components/element/ImageElement/ImageOutline/index.tsx`。
 * 只去掉 `'use client'` 与 TypeScript 类型；`clipShape.createPath!` 的非空断言
 * 随类型检查一起去掉。
 */
import { useClipImage } from '../useClipImage.js';
import { ImageRectOutline } from './image-rect-outline.jsx';
import { ImageEllipseOutline } from './image-ellipse-outline.jsx';
import { ImagePolygonOutline } from './image-polygon-outline.jsx';

/**
 * Image outline dispatcher based on clip shape type
 */
export function ImageOutline({ elementInfo }) {
  const { clipShape } = useClipImage(elementInfo);

  return (
    <div className="image-outline">
      {clipShape.type === 'rect' && (
        <ImageRectOutline
          width={elementInfo.width}
          height={elementInfo.height}
          radius={clipShape.radius}
          outline={elementInfo.outline}
        />
      )}
      {clipShape.type === 'ellipse' && (
        <ImageEllipseOutline
          width={elementInfo.width}
          height={elementInfo.height}
          outline={elementInfo.outline}
        />
      )}
      {clipShape.type === 'polygon' && (
        <ImagePolygonOutline
          width={elementInfo.width}
          height={elementInfo.height}
          outline={elementInfo.outline}
          createPath={clipShape.createPath}
        />
      )}
    </div>
  );
}
