/**
 * 逐字移植自参考 `components/slide-renderer/use-resolved-slide.ts` 的公开接口。
 *
 * 参考项目的实现完全建立在 `@/lib/media/*` 那套生成媒体编排上（任务表、
 * 资产租约、生成权限），目标项目没有这套东西，因此 `resolveSlideMediaState`
 * 退化为「把 assetResolver 的结果写回元素 src」，并保持同样的返回结构：
 * `{ slide, byElementId, backgroundResolution }`。
 *
 * 具体差异：
 *   - `byElementId[id].resolution` 对非空 src 恒为 `{ kind: 'url' }`；
 *   - `task` 恒为 undefined（没有生成任务）；
 *   - `posterResolution` 由封面地址解析得出。
 * 这让沿用参考结构的调用方（例如自己实现 renderImage 回调）仍然拿到同样的
 * 判别联合，四条渲染分支（骨架 / 禁用 / 失败 / 正常）中只有「正常」会出现。
 */
import { useMemo } from 'react';
import { resolveAssetWith } from './asset-resolver.js';
import { renderableMediaUrl, resolveMediaRef } from './media-ref.js';

export function resolveSlideMediaState(slide, _stageId, _tasks, options = {}) {
  const resolver = options.assetResolver;
  const byElementId = {};
  const backgroundRef =
    slide.background?.type === 'image' ? slide.background.image?.src : undefined;
  const resolvedBackgroundRef = resolveAssetWith(resolver, backgroundRef);
  const backgroundResolution = backgroundRef ? resolveMediaRef(resolvedBackgroundRef) : undefined;
  const backgroundSrc = backgroundResolution
    ? (renderableMediaUrl(backgroundResolution) ?? '')
    : undefined;
  const background =
    slide.background?.type === 'image' &&
    slide.background.image &&
    backgroundSrc !== undefined &&
    backgroundSrc !== slide.background.image.src
      ? {
          ...slide.background,
          image: { ...slide.background.image, src: backgroundSrc },
        }
      : slide.background;

  const elements = slide.elements.map((element) => {
    if (element.type !== 'image' && element.type !== 'video') return element;

    const sourceRef = resolveAssetWith(resolver, element.src);
    const resolution = resolveMediaRef(sourceRef);
    const posterRef = resolveAssetWith(resolver, element.poster);
    const posterResolution = element.poster ? resolveMediaRef(posterRef) : undefined;

    if (element.id) byElementId[element.id] = { ref: element.src, resolution, posterResolution };

    const src = renderableMediaUrl(resolution) ?? '';
    if (element.type === 'image') return src === element.src ? element : { ...element, src };

    const poster = posterResolution ? renderableMediaUrl(posterResolution) : element.poster;
    if (src === element.src && poster === element.poster) return element;
    const next = { ...element, src };
    if (poster === undefined) delete next.poster;
    else next.poster = poster;
    return next;
  });

  return {
    slide:
      background === slide.background &&
      elements.every((element, index) => element === slide.elements[index])
        ? slide
        : { ...slide, background, elements },
    byElementId,
    backgroundResolution,
  };
}

export function resolveSlideMedia(slide, stageId, tasks, options = {}) {
  return resolveSlideMediaState(slide, stageId, tasks, options).slide;
}

export function useResolvedSlideMedia(slide, options = {}) {
  const { assetResolver } = options;
  return useMemo(
    () => resolveSlideMediaState(slide, undefined, {}, { assetResolver }),
    [slide, assetResolver],
  );
}

export function useResolvedSlide(slide, options = {}) {
  return useResolvedSlideMedia(slide, options).slide;
}
