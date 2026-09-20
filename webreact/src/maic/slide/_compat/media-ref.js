/**
 * 移植补充：媒体地址解析的等价层。
 *
 * 参考项目里 `@/lib/media/resolve-media-ref.ts` 管理「生成中占位符 → 任务对象
 * URL」的解析，并把结果收敛成 `MediaResolution` 判别联合。
 * `BaseImageElement` / `BaseVideoElement` / `RendererScreenCanvas` 依赖它的形状
 * 来决定骨架屏 / 禁用 / 失败 / 正常四条分支。
 *
 * 参考项目 `RendererScreenCanvas` 的 `PlaybackImageContent` / `PlaybackVideoContent`
 * 走的是 `renderImage` / `renderVideo` 回调注入路线；目标项目的
 * `MaicSlideSurface` 直接渲染 base 元素（即参考 `ScreenCanvas` 那条路径），
 * 因此这里把解析层退化为最简语义：
 *
 *   - 非空 src ⇒ `{ kind: 'url' }`，`renderableMediaUrl` 直接给出该地址；
 *   - 空 src   ⇒ `{ kind: 'placeholder' }`，与参考项目「没有可用地址」的
 *     渲染结果（骨架/黑底播放图标）一致；
 *   - `explicit` 允许调用方直接指定一个 resolution，用于将来接 CampusMate
 *     素材接口时复用同一套四条分支。
 *
 * `mediaResolutionCanRetry` 在参考项目里判断任务是否可重试。目标项目没有生成
 * 任务可重试，因此恒为 false —— 重试按钮不会出现（与参考项目里「没有任务就
 * 没有重试」的行为一致）。
 */

export const MISSING_ASSET_LEASE = { status: 'missing' };

export function renderableMediaUrl(resolution) {
  if (!resolution) return undefined;
  if (resolution.kind === 'url') return resolution.url;
  return undefined;
}

export function isMediaResolutionRenderable(resolution) {
  return !!resolution && resolution.kind === 'url' && !!resolution.url;
}

export function mediaResolutionCanRetry() {
  return false;
}

export function mediaResolutionHasLiveTask() {
  return false;
}

/**
 * 计算一个媒体引用的解析结果。
 *
 * @param src 已经过 assetResolver 的地址（`_compat/asset-resolver.js`）
 * @param explicit 可选的显式 resolution，优先级最高
 */
export function resolveMediaRef(src, explicit) {
  if (explicit) return explicit;
  if (typeof src === 'string' && src.length > 0) {
    return { kind: 'url', url: src };
  }
  return { kind: 'placeholder' };
}

export function isConcreteMediaAddress(src) {
  if (typeof src !== 'string' || !src) return false;
  return /^(https?:|data:|blob:|\/)/i.test(src);
}

/**
 * 目标项目里没有可重试的生成任务；保留同名函数让被移植组件的调用点保持原样。
 */
export function retryMediaTask() {
  return undefined;
}

export function mediaRetryTarget(elementId, sceneId, sceneData) {
  return { elementId, sceneId, sceneData };
}

/**
 * 参考项目用于把「生成被拒绝」的原因码映射成 i18n key。
 * 目标项目没有生成编排，永远没有拒绝原因。
 */
export function mediaFailureNoticeKey() {
  return undefined;
}
