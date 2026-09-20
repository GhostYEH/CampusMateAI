/**
 * 移植补充：canvas store 的最小等价层。
 *
 * 参考项目 `@/lib/store/canvas` 是 Zustand store。slide 播放路径从它读两类状态：
 *
 *   1. 视频播放焦点 —— `BaseVideoElement` 的
 *      `use.playingVideoElementId()` / `getState().pauseVideo()`：视频从不自动
 *      播放，只有课堂动作 `play_video` 把它设为当前播放元素时才开始播放，
 *      并配一段「轻按」缩放动画；
 *   2. 播放期视觉特效 —— `ScreenCanvas` / `RendererScreenCanvas` 的
 *      `laserElementId` / `laserOptions` / `zoomTarget` / `highlightedElementIds`
 *      / `highlightOptions` / `spotlightElementId` / `spotlightOptions` /
 *      `canvasScale`。
 *
 * 目标项目没有 Zustand，也不想为此新增依赖，因此这里用
 * `useSyncExternalStore` 复刻参考项目实际用到的那个 API 子集（`use.*` 选择器
 * 与 `getState()`）。默认值 = 「没有任何特效」：`canvasScale` 为 `undefined`，
 * 画布走自动适配（与参考 `useViewportSize` 的 fitScale 分支一致）；其余为
 * `null` / `[]`。宿主可以用下面导出的 setter 驱动这些特效。
 *
 * 行为与参考一致：同一时刻只有一个视频处于「请求播放」状态；元素卸载时清空。
 */
import { useSyncExternalStore } from 'react';

const DEFAULT_STATE = {
  canvasScale: undefined,
  playingVideoElementId: '',
  highlightedElementIds: [],
  highlightOptions: null,
  spotlightElementId: '',
  spotlightOptions: null,
  laserElementId: '',
  laserOptions: null,
  zoomTarget: null,
};

function createCanvasStore() {
  let state = { ...DEFAULT_STATE };
  const listeners = new Set();

  const emit = () => {
    for (const listener of Array.from(listeners)) listener();
  };

  const subscribe = (listener) => {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  };

  const setState = (patch) => {
    let changed = false;
    for (const key of Object.keys(patch)) {
      if (!Object.is(state[key], patch[key])) {
        changed = true;
        break;
      }
    }
    if (!changed) return;
    state = { ...state, ...patch };
    emit();
  };

  const select = (key) =>
    useSyncExternalStore(
      subscribe,
      () => state[key],
      () => state[key],
    );

  return {
    subscribe,
    getState: () => state,
    setState,
    playVideo: (elementId) => setState({ playingVideoElementId: elementId }),
    pauseVideo: () => setState({ playingVideoElementId: '' }),
    clearPlayingIfMatches: (elementId) => {
      if (state.playingVideoElementId === elementId) setState({ playingVideoElementId: '' });
    },
    setCanvasScale: (canvasScale) => setState({ canvasScale }),
    setHighlightedElementIds: (highlightedElementIds) => setState({ highlightedElementIds }),
    setHighlightOptions: (highlightOptions) => setState({ highlightOptions }),
    setSpotlight: (spotlightElementId, spotlightOptions) =>
      setState({ spotlightElementId, spotlightOptions }),
    setLaser: (laserElementId, laserOptions) => setState({ laserElementId, laserOptions }),
    setZoomTarget: (zoomTarget) => setState({ zoomTarget }),
    resetEffects: () =>
      setState({
        highlightedElementIds: DEFAULT_STATE.highlightedElementIds,
        highlightOptions: null,
        spotlightElementId: '',
        spotlightOptions: null,
        laserElementId: '',
        laserOptions: null,
        zoomTarget: null,
      }),
    use: {
      canvasScale: () => select('canvasScale'),
      playingVideoElementId: () => select('playingVideoElementId'),
      highlightedElementIds: () => select('highlightedElementIds'),
      highlightOptions: () => select('highlightOptions'),
      spotlightElementId: () => select('spotlightElementId'),
      spotlightOptions: () => select('spotlightOptions'),
      laserElementId: () => select('laserElementId'),
      laserOptions: () => select('laserOptions'),
      zoomTarget: () => select('zoomTarget'),
    },
  };
}

export const useCanvasStore = createCanvasStore();

/**
 * 稳定的空引用：画布的选择器在「没有特效」时会返回它，而不是每次渲染新建
 * 一个 `[]` / `{}`。`ScreenCanvas` 依赖 referential identity 来决定是否重算
 * 几何，这里必须共用同一个实例。
 */
export const EMPTY_EFFECT_LIST = [];
export const NO_EFFECT_OPTIONS = null;
