/**
 * 移植自参考项目 `lib/edit/visible-client-rect.ts`。
 * 仅擦除 TypeScript 类型标注（interface / `: Element` / 泛型）。
 */

/** Axis-aligned box in viewport coordinates. */

export function intersectClientBoxes(a, b) {
  const left = Math.max(a.left, b.left);
  const top = Math.max(a.top, b.top);
  const right = Math.min(a.left + a.width, b.left + b.width);
  const bottom = Math.min(a.top + a.height, b.top + b.height);
  return {
    left,
    top,
    width: Math.max(0, right - left),
    height: Math.max(0, bottom - top),
  };
}

function clipsOverflow(value) {
  return value === 'hidden' || value === 'clip' || value === 'auto' || value === 'scroll';
}

/** Return the part of a node that is not clipped by an overflow ancestor. */
export function visibleClientRect(node) {
  const rect = node.getBoundingClientRect();
  let box = {
    left: rect.left,
    top: rect.top,
    width: rect.width,
    height: rect.height,
  };
  let element = node.parentElement;
  while (element) {
    const style = getComputedStyle(element);
    if (clipsOverflow(style.overflowX) || clipsOverflow(style.overflowY)) {
      const clip = element.getBoundingClientRect();
      box = intersectClientBoxes(box, {
        left: clip.left,
        top: clip.top,
        width: clip.width,
        height: clip.height,
      });
    }
    element = element.parentElement;
  }
  return box;
}
