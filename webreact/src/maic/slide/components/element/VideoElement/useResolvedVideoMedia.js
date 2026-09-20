/**
 * 参考文件：`components/slide-renderer/components/element/VideoElement/useResolvedVideoMedia.ts`
 *
 * 接口与返回结构逐字一致：`mediaRef` / `task` / `resolution` /
 * `posterResolution` / `resolvedSrc` / `resolvedPoster`。
 *
 * 被替换的实现内部：参考项目要从媒体生成 store 里按 element 找生成任务
 * （`resolveVideoMediaForElement`），再经 `useResolvedMediaRef` 解析成
 * `MediaResolution`。目标项目没有这套编排，视频与封面地址由 `assetResolver`
 * 提供，因此 `task` 恒为 undefined，`mediaRef` 取解析后的 sourceRef。
 */
import { useMemo } from 'react';
import { useAssetResolver, resolveAssetWith } from '../../../_compat/asset-resolver.js';
import { renderableMediaUrl, resolveMediaRef } from '../../../_compat/media-ref.js';

/** Shared direct-video binding used by both the read-only and editor elements. */
export function useResolvedVideoMedia(element, assetResolver) {
  return useMemo(() => {
    const sourceRef = resolveAssetWith(assetResolver, element.src);
    const resolution = resolveMediaRef(sourceRef);
    // 参考项目只在 posterRef 存在时才解析封面（`videoBinding?.posterRef !== undefined`）。
    const posterRef = element.poster ? resolveAssetWith(assetResolver, element.poster) : undefined;
    const posterResolution = posterRef !== undefined ? resolveMediaRef(posterRef) : undefined;
    return {
      mediaRef: sourceRef,
      task: undefined,
      resolution,
      posterResolution,
      resolvedSrc: renderableMediaUrl(resolution),
      resolvedPoster: posterResolution ? renderableMediaUrl(posterResolution) : undefined,
    };
  }, [element.src, element.poster, assetResolver]);
}

/** 组件内使用的便捷版本：从 context 取 assetResolver。 */
export function useResolvedVideoMediaFromContext(element) {
  const assetResolver = useAssetResolver();
  return useResolvedVideoMedia(element, assetResolver);
}
