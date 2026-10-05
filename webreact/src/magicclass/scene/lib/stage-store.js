import { createStore } from "./store.js";

/**
 * 参考项目 `lib/store/stage.ts` 的极小切片。
 *
 * 原 store 有 51KB（播放、编辑、生成、持久化全在里面），本移植层只用到三个成员：
 *   - `stage`          （classroom-complete 取 stage.name 作为标题）
 *   - `scenes`         （hero 取本 PBL 场景之前的场景来算 quiz 快照）
 *   - `updateScene`    （PBL 把新的 projectV2 写回场景内容）
 *
 * 这是"zustand store -> 普通 React 状态"的替换：签名保持一致，组件照旧调用
 * `useStageStore.getState().scenes` / `useStageStore((s) => s.scenes)`。
 * 未移植的成员（stage 增删、播放控制、持久化）不在本层职责内。
 */
export const useStageStore = createStore((set, get) => ({
  stage: null,
  scenes: [],

  setStage: (stage) => set({ stage }),

  setScenes: (scenes) => set({ scenes }),

  /** 与参考实现同签名：按 id 浅合并 patch，未命中则不动。 */
  updateScene: (sceneId, patch) =>
    set((state) => ({
      scenes: state.scenes.map((scene) =>
        scene.id === sceneId ? { ...scene, ...patch } : scene,
      ),
    })),

  getScenes: () => get().scenes,
}));
