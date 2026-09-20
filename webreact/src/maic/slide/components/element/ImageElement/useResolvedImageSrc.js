/**
 * 参考文件：`components/slide-renderer/components/element/ImageElement/useResolvedImageSrc.ts`
 *
 * 接口与返回结构和参考逐字一致（`resolvedSrc` / `isPlaceholder` /
 * `resolvedFromAsset` / `task` / `resolution`），两条导出（纯函数
 * `resolveImageSrc` 与 hook `useResolvedImageSrc`）都保留。
 *
 * 被替换的实现内部：参考项目要订阅媒体生成 store（`gen_img_*` 占位符 →
 * 生成任务 objectUrl）、渲染租约和生成开关；目标项目没有这套编排，图片地址
 * 由 `MaicSlideSurface` 的 `assetResolver` 给出。因此：
 *   - 纯函数版本接受一个可选的 `assetResolver`，替代原来的 `assetUrl` 参数；
 *   - `task` 恒为 undefined，`resolution` 只有 `url` / `placeholder` 两种，
 *     于是四条渲染分支里骨架屏与失败分支在本项目不会被触发（与「没有生成任务」
 *     的真实情况一致）。
 */
import { useMemo } from 'react';
import { useAssetResolver, resolveAssetWith } from '../../../_compat/asset-resolver.js';
import { renderableMediaUrl, resolveMediaRef } from '../../../_compat/media-ref.js';

/**
 * Pure resolver — no hooks. Given an image element plus the already-resolved
 * stageId and possibly-keyed task, computes the final resolution shape.
 * Splitting this out of the hook keeps the logic unit-testable in a plain
 * node environment (no RTL/jsdom needed).
 *
 * Direct and relative browser addresses pass through. Opaque references are
 * rendered only after the asset lease or task supplies a concrete URL.
 */
export function resolveImageSrc(elementInfo, assetResolver) {
  const src = resolveAssetWith(assetResolver, elementInfo.src);
  const resolution = resolveMediaRef(src);
  const resolvedSrc = renderableMediaUrl(resolution) ?? '';
  return {
    resolvedSrc,
    isPlaceholder: resolution.kind === 'placeholder',
    resolvedFromAsset: resolution.kind === 'url',
    task: undefined,
    resolution,
  };
}

/**
 * Resolve a slide image element's src so the read-only playback variant can pick
 * between its skeleton / error / disabled / image branches.
 *
 * The asset resolver is read from context (see `_compat/asset-resolver.js`), so
 * the component signature stays exactly the one the reference exposes.
 */
export function useResolvedImageSrc(elementInfo) {
  const assetResolver = useAssetResolver();
  return useMemo(() => resolveImageSrc(elementInfo, assetResolver), [elementInfo, assetResolver]);
}
