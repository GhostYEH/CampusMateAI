import { createStore } from './store.js';

/**
 * 移植自参考项目 `lib/store/interactive-iframe-pool.ts`。
 *
 * Keep-alive pool for interactive scene iframes (#619).
 *
 * Interactive scenes render their content in an `<iframe>`. When that element
 * unmounts or is re-parented (Pro mode toggle, scene switch and back, any
 * PlaybackChromeRoot remount) the browser drops the document and re-parses /
 * re-runs from scratch, losing in-iframe state. To avoid that, the actual
 * iframe elements live in a single stable host (`InteractiveIframeHost`)
 * mounted at the `Stage` root, outside the reconciled scene subtree. This store
 * is the coordination layer between the in-tree placeholder (`InteractiveRenderer`)
 * and that host: it tracks, per scene, the content to render, the live on-screen
 * rect to position the iframe over, and whether it should currently be visible.
 *
 * Entries are keyed by sceneId and persist across scene/mode changes — a scene's
 * iframe is only rebuilt when its content actually changes. A small LRU cap
 * bounds how many documents stay resident in memory.
 *
 * 机械改写：`zustand` 的 `create` -> 本层的 `createStore`（同样接受 `(set, get)`，
 * 同样暴露 `getState` 与 selector hook），TypeScript 类型全部擦除。
 */

export const IFRAME_POOL_CAP = 3;

/**
 * Drop the least-recently-touched entries until at most CAP remain. The active
 * scene is never evicted (its iframe is on screen). Returns a new entries map.
 */
function evictLru(entries, activeSceneId) {
  const ids = Object.keys(entries);
  if (ids.length <= IFRAME_POOL_CAP) return entries;
  const evictable = ids
    .filter((id) => id !== activeSceneId)
    .sort((a, b) => entries[a].tick - entries[b].tick);
  const next = { ...entries };
  let overflow = ids.length - IFRAME_POOL_CAP;
  for (const id of evictable) {
    if (overflow <= 0) break;
    delete next[id];
    overflow--;
  }
  return next;
}

export const useInteractiveIframePool = createStore((set) => ({
  entries: {},
  activeSceneId: null,
  tick: 0,

  mount: (sceneId, input) =>
    set((state) => {
      const tick = state.tick + 1;
      const existing = state.entries[sceneId];
      // Same content already loaded: just refresh recency. Crucially we keep the
      // existing srcDoc/src reference so the host never re-sets it (which would
      // reload the iframe). String `===` is by value, so a remount that produces
      // an equal-but-new srcDoc string still hits this keep-alive fast path.
      if (existing && existing.srcDoc === input.srcDoc && existing.src === input.src) {
        const entries = { ...state.entries, [sceneId]: { ...existing, tick } };
        return { entries, tick };
      }
      // New scene, or content changed: (re)build the entry. A content change here
      // is the one intended reload path.
      const entry = {
        srcDoc: input.srcDoc,
        src: input.src,
        rect: existing?.rect ?? null,
        clip: existing?.clip ?? null,
        owner: existing?.owner ?? null,
        tick,
      };
      const entries = evictLru({ ...state.entries, [sceneId]: entry }, state.activeSceneId);
      return { entries, tick };
    }),

  setRect: (sceneId, rect, clip = rect) =>
    set((state) => {
      const existing = state.entries[sceneId];
      if (!existing) return {};
      const r = existing.rect;
      const c = existing.clip;
      if (
        r &&
        c &&
        r.left === rect.left &&
        r.top === rect.top &&
        r.width === rect.width &&
        r.height === rect.height &&
        c.left === clip.left &&
        c.top === clip.top &&
        c.width === clip.width &&
        c.height === clip.height
      ) {
        return {};
      }
      return { entries: { ...state.entries, [sceneId]: { ...existing, rect, clip } } };
    }),

  claim: (sceneId, owner) =>
    set((state) => {
      const existing = state.entries[sceneId];
      if (!existing || existing.owner === owner) return {};
      return { entries: { ...state.entries, [sceneId]: { ...existing, owner } } };
    }),

  release: (sceneId, owner) =>
    set((state) => {
      const existing = state.entries[sceneId];
      // Only the current owner may release. A stale placeholder (whose unmount
      // cleanup runs after a newer one already re-claimed during the mode
      // cross-fade) finds owner !== its id and no-ops, so the live iframe stays.
      if (!existing || existing.owner !== owner) return {};
      return { entries: { ...state.entries, [sceneId]: { ...existing, owner: null } } };
    }),

  setActive: (sceneId) => set({ activeSceneId: sceneId }),

  evict: (sceneId) =>
    set((state) => {
      if (!state.entries[sceneId]) return {};
      const entries = { ...state.entries };
      delete entries[sceneId];
      const activeSceneId = state.activeSceneId === sceneId ? null : state.activeSceneId;
      return { entries, activeSceneId };
    }),

  reset: () => set({ entries: {}, activeSceneId: null, tick: 0 }),
}));
