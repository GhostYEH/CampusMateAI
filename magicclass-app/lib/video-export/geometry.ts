/**
 * Pure element-geometry resolution for the video-timeline compiler.
 *
 * Resolves a slide element's percentage geometry (0–100 space) so effect
 * segments (spotlight/laser) can carry the target's position into the IR. This
 * is a faithful reimplementation of the runtime's calculation — the app copy
 * (`lib/utils/geometry.ts`) imports a host-app path and the packaged copy
 * (`@magicclass/renderer`) pulls a render backend, so both are unreachable under
 * this module's purity boundary. The math is ~15 lines and must stay identical
 * to the runtime's, so it is mirrored here rather than imported.
 *
 * The runtime uses a fixed 1000px width base and a 16:9 (0.5625) height ratio,
 * independent of a slide's own `viewportSize`/`viewportRatio`, so we do the same
 * — the spotlight/laser overlays position against this same base.
 *
 * Pure: type-only import from `@magicclass/dsl`.
 */
import type { PPTElement } from '@magicclass/dsl';
import type { PercentageGeometry } from './ir';

/** Height ratio the runtime derives the vertical base from (16:9). */
const VIEWPORT_RATIO = 0.5625;

/**
 * Percentage geometry (0–100) for a single positioned element. Returns null for
 * elements without `left/top/width/height` (e.g. some line elements), matching
 * the runtime helper.
 */
export function getElementPercentageGeometry(
  element: PPTElement,
  viewportSize = 1000,
): PercentageGeometry | null {
  if (element.type === 'line') {
    const points: [number, number][] = [element.start, element.end];
    // Match the rendered path's precedence; inactive control fields must not move the pointer.
    if (element.broken) points.push(element.broken);
    else if (element.broken2) {
      const horizontal = Math.max(element.start[0], element.end[0]) >= Math.max(element.start[1], element.end[1]);
      if (horizontal) points.push([element.broken2[0], element.start[1]], [element.broken2[0], element.end[1]]);
      else points.push([element.start[0], element.broken2[1]], [element.end[0], element.broken2[1]]);
    } else if (element.curve) points.push(element.curve);
    else if (element.cubic) points.push(...element.cubic);
    const xs = points.map((point) => point[0]);
    const ys = points.map((point) => point[1]);
    const x = ((element.left + Math.min(...xs)) / viewportSize) * 100;
    const y = ((element.top + Math.min(...ys)) / (viewportSize * VIEWPORT_RATIO)) * 100;
    const w = ((Math.max(...xs) - Math.min(...xs)) / viewportSize) * 100;
    const h = ((Math.max(...ys) - Math.min(...ys)) / (viewportSize * VIEWPORT_RATIO)) * 100;
    return { x, y, w, h, centerX: x + w / 2, centerY: y + h / 2 };
  }
  if (
    !('left' in element) ||
    !('top' in element) ||
    !('width' in element) ||
    !('height' in element)
  ) {
    return null;
  }

  const { left, top, width, height } = element;

  const x = (left / viewportSize) * 100;
  const y = (top / (viewportSize * VIEWPORT_RATIO)) * 100;
  const w = (width / viewportSize) * 100;
  const h = (height / (viewportSize * VIEWPORT_RATIO)) * 100;

  return { x, y, w, h, centerX: x + w / 2, centerY: y + h / 2 };
}

/**
 * Find an element by id in a slide's element list and return its percentage
 * geometry, or null when the element is absent or has no position.
 */
export function findElementGeometry(
  elements: PPTElement[],
  elementId: string,
  viewportSize = 1000,
): PercentageGeometry | null {
  const element = elements.find((el) => el.id === elementId);
  if (!element) return null;
  return getElementPercentageGeometry(element, viewportSize);
}

/** An element's placement: percentage geometry + rotation (degrees). */
export interface ElementPlacement {
  geometry: PercentageGeometry;
  /** Rotation in degrees; 0 for elements that carry no `rotate`. */
  rotate: number;
}

/**
 * Find an element and return both its percentage geometry and rotation, or null
 * when the element is absent or unpositioned. Used to place `play_video` clips
 * (position + size + rotation) into the IR so an emitter needs no scene DSL.
 */
export function findElementPlacement(
  elements: PPTElement[],
  elementId: string,
  viewportSize = 1000,
): ElementPlacement | null {
  const element = elements.find((el) => el.id === elementId);
  if (!element) return null;
  const geometry = getElementPercentageGeometry(element, viewportSize);
  if (!geometry) return null;
  const rotate = 'rotate' in element && typeof element.rotate === 'number' ? element.rotate : 0;
  return { geometry, rotate };
}
