/**
 * 移植补充：幻灯片背景样式。
 *
 * 逐字移植自参考 `lib/hooks/use-slide-background-style.ts` 的样式分支
 * （solid / image / gradient），只去掉 TypeScript 类型。
 *
 * 替换掉的依赖：`@/lib/contexts/media-stage-context`、
 * `@/lib/media/resolve-media-ref`、`@/lib/store/media-generation`、
 * `@/lib/store/settings` —— 这一整套是参考项目的生成媒体编排。目标项目里图片
 * 背景地址由 `MaicSlideSurface` 的 `assetResolver` 提供，解析后直接使用；
 * 「生成被关闭」这个开关在 CampusMate 不存在，因此等价于参考项目里
 * `imageGenerationEnabled = true` 的分支。
 */
import { useMemo } from 'react';
import { useAssetResolver, resolveAssetWith } from './asset-resolver.js';
import { renderableMediaUrl, resolveMediaRef } from './media-ref.js';

export function useSlideBackgroundStyle(background) {
  const assetResolver = useAssetResolver();
  const ref = background?.type === 'image' ? background.image?.src : undefined;
  const resolvedRef = resolveAssetWith(assetResolver, ref);
  const resolution = resolveMediaRef(resolvedRef);
  const resolvedSrc = renderableMediaUrl(resolution);

  const backgroundStyle = useMemo(() => {
    if (!background) return { backgroundColor: '#fff' };

    const { type, color, image, gradient } = background;

    // Solid color background
    if (type === 'solid') return { backgroundColor: color };

    // Image background mode
    // Includes: background image, background size, whether to repeat
    if (type === 'image' && image) {
      const { size } = image;
      const src = resolvedSrc ?? '';
      if (!src) return { backgroundColor: '#fff' };
      if (size === 'repeat') {
        return {
          backgroundImage: `url(${src})`,
          backgroundRepeat: 'repeat',
          backgroundSize: 'contain',
        };
      }
      return {
        backgroundImage: `url(${src})`,
        backgroundRepeat: 'no-repeat',
        backgroundSize: size || 'cover',
      };
    }

    // Gradient background
    if (type === 'gradient' && gradient) {
      const { type: gradientType, colors, rotate } = gradient;
      const list = colors.map((item) => `${item.color} ${item.pos}%`);

      if (gradientType === 'radial') {
        return { backgroundImage: `radial-gradient(${list.join(',')})` };
      }
      return {
        backgroundImage: `linear-gradient(${rotate}deg, ${list.join(',')})`,
      };
    }

    return { backgroundColor: '#fff' };
  }, [background, resolvedSrc]);

  return {
    backgroundStyle,
  };
}
