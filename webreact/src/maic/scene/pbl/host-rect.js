/**
 * 移植自参考项目 `components/scene-renderers/pbl/v2/host-rect.ts`。
 * 仅擦除 TypeScript interface / 类型标注。
 *
 * PBL v2 — docked workspace/completion host-rect tracking helpers.
 *
 * The workspace and completion phases render in a `position: fixed` frame that
 * is portaled out of the scene subtree (so the fullscreen expand/collapse can
 * animate without remounting the chat). While docked it is positioned over the
 * stage's host box via a JS-measured rect. These helpers keep that tracking
 * cheap and correct.
 */

/**
 * Whether two host rects are identical. Used as a dirty-check so the per-frame
 * position poll only triggers React state updates when the host box actually
 * moved or resized — otherwise an idle docked frame would re-render every
 * animation frame. Pure, for unit testing.
 */
export function rectsEqual(a, b) {
  return a.left === b.left && a.top === b.top && a.width === b.width && a.height === b.height;
}
