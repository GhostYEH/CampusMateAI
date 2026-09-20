/**
 * 移植补充：`assetResolver` 接入点。
 *
 * 参考项目的图片/视频地址由 `@/lib/media/*` 一套生成媒体编排解决（任务队列、
 * 资产租约、生成开关……）。CampusMate 没有那套编排，素材由自己的 API 提供，
 * 所以这里把上游的 `resolvedSrc` 解析链替换成一个可注入的解析钩子：
 *
 *   - 未提供 `assetResolver` 时，`resolveAsset` 原样返回 src（等于参考项目里
 *     「具体地址直接透传」的那条分支）；
 *   - 提供时，所有图片/视频/背景图 src 都会经过它，`BaseImageElement` /
 *     `BaseVideoElement` / 视频封面 / 背景图 / SVG `<pattern>` 均覆盖。
 *
 * 用 context 而不是层层透传 props，是为了让被移植的叶子组件保持参考文件里的
 * props 形状与返回结构（context Provider 不产生额外 DOM）。
 */
import { createContext, useContext } from 'react';

const identity = (src) => src;

const AssetResolverContext = createContext(identity);

export const AssetResolverProvider = AssetResolverContext.Provider;

export function useAssetResolver() {
  return useContext(AssetResolverContext) ?? identity;
}

/** 供非组件代码（纯函数、SSR 之外的工具）使用的安全包装。 */
export function resolveAssetWith(resolver, src) {
  if (src === undefined || src === null || src === '') return src;
  if (typeof resolver !== 'function') return src;
  try {
    const resolved = resolver(src);
    return typeof resolved === 'string' && resolved ? resolved : src;
  } catch {
    return src;
  }
}

/** 把一个 slide/element 上所有图片来源替换为 `assetResolver` 的结果。 */
export function withResolvedAssetSrc(element, resolver) {
  if (!element || typeof element !== 'object') return element;
  if (element.type !== 'image' && element.type !== 'video') return element;

  const src = resolveAssetWith(resolver, element.src);
  const poster = resolveAssetWith(resolver, element.poster);
  if (src === element.src && poster === element.poster) return element;
  return { ...element, src, poster };
}
