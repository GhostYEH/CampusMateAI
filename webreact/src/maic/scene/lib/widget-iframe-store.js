import { createStore } from './store.js';

/**
 * 移植自参考项目 `lib/store/widget-iframe.ts`。
 *
 * Widget iframe messaging store.
 * Tracks iframe postMessage callbacks per scene to prevent race conditions
 * when switching between interactive scenes.
 *
 * 机械改写：zustand `create` -> `createStore`，TypeScript 类型擦除。
 */
export const useWidgetIframeStore = createStore((set, get) => ({
  /** Callbacks keyed by sceneId for targeted postMessage communication */
  sendMessageByScene: {},
  /** Currently active scene ID (used for fallback/legacy support) */
  activeSceneId: null,
  /** Register an iframe callback for a specific scene */
  registerIframe: (sceneId, callback) =>
    set((state) => {
      if (callback === null) {
        // Unregister: remove from map
        const updated = { ...state.sendMessageByScene };
        delete updated[sceneId];
        return { sendMessageByScene: updated };
      }
      // Register: add to map
      return {
        sendMessageByScene: { ...state.sendMessageByScene, [sceneId]: callback },
      };
    }),
  /** Set the active scene ID */
  setActiveScene: (sceneId) => set({ activeSceneId: sceneId }),
  /** Get sendMessage callback for a specific scene (or current active scene) */
  getSendMessage: (sceneId) => {
    const state = get();
    const targetId = sceneId ?? state.activeSceneId;
    if (!targetId) return null;
    return state.sendMessageByScene[targetId] ?? null;
  },
}));
