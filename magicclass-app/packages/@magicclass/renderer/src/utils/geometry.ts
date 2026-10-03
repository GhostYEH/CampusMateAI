import type { PPTElement } from '@magicclass/dsl';

/**
 * Percentage-based geometry (0-100 coordinate system)
 * Used by spotlight/laser overlays for responsive positioning.
 */
export interface PercentageGeometry {
  x: number;
  y: number;
  w: number;
  h: number;
  centerX: number;
  centerY: number;
}

export function getElementPercentageGeometry(
  element: PPTElement,
  viewportSize: number = 1000,
  viewportRatio: number = 0.5625,
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
    const y = ((element.top + Math.min(...ys)) / (viewportSize * viewportRatio)) * 100;
    const w = ((Math.max(...xs) - Math.min(...xs)) / viewportSize) * 100;
    const h = ((Math.max(...ys) - Math.min(...ys)) / (viewportSize * viewportRatio)) * 100;
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
  const y = (top / (viewportSize * viewportRatio)) * 100;
  const w = (width / viewportSize) * 100;
  const h = (height / (viewportSize * viewportRatio)) * 100;

  const centerX = x + w / 2;
  const centerY = y + h / 2;

  return { x, y, w, h, centerX, centerY };
}

export function findElementGeometry(
  elements: PPTElement[],
  elementId: string,
  viewportSize: number = 1000,
  viewportRatio: number = 0.5625,
): PercentageGeometry | null {
  const element = elements.find((el) => el.id === elementId);
  if (!element) return null;
  return getElementPercentageGeometry(element, viewportSize, viewportRatio);
}

export function findNearestCorner(geometry: PercentageGeometry): {
  x: number;
  y: number;
} {
  const { centerX, centerY } = geometry;

  const corners = [
    { x: 0, y: 0 },
    { x: 100, y: 0 },
    { x: 0, y: 100 },
    { x: 100, y: 100 },
  ];

  let minDistance = Infinity;
  let nearestCorner = corners[0];

  for (const corner of corners) {
    const distance = Math.sqrt(Math.pow(corner.x - centerX, 2) + Math.pow(corner.y - centerY, 2));
    if (distance < minDistance) {
      minDistance = distance;
      nearestCorner = corner;
    }
  }

  return nearestCorner;
}
