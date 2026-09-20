/**
 * 逐字移植自参考
 * `components/slide-renderer/components/element/ShapeElement/PatternDefs.tsx`。
 *
 * 机械改写：去掉 TypeScript 类型；`src` 先过一遍 `assetResolver`，让形状里的
 * SVG `<pattern>` 位图也用同一套素材地址解析（参考项目这里直接用原始 src，
 * 因为它的 src 在进入渲染层之前已被媒体编排解析过）。
 */
import { useAssetResolver, resolveAssetWith } from '../../../_compat/asset-resolver.js';

export function PatternDefs({ id, src }) {
  const assetResolver = useAssetResolver();
  const resolvedSrc = resolveAssetWith(assetResolver, src);

  return (
    <pattern
      id={id}
      patternContentUnits="objectBoundingBox"
      patternUnits="objectBoundingBox"
      width="1"
      height="1"
    >
      <image href={resolvedSrc} width="1" height="1" preserveAspectRatio="xMidYMid slice" />
    </pattern>
  );
}
