export function getDockScale(pointerDistance, distance = 120, baseItemSize = 36, magnification = 60) {
  if (!Number.isFinite(pointerDistance) || distance <= 0 || baseItemSize <= 0 || magnification <= 0) return 1;

  const proximity = Math.max(0, 1 - Math.abs(pointerDistance) / distance);
  return 1 + (magnification / baseItemSize - 1) * proximity;
}

export function getFloatingNavWidth({ contentWidth, viewportWidth, gutter = 12 }) {
  const content = Number.isFinite(contentWidth) ? Math.max(0, contentWidth) : 0;
  const viewport = Number.isFinite(viewportWidth) ? Math.max(0, viewportWidth) : 0;
  const sideGutter = Number.isFinite(gutter) ? Math.max(0, gutter) : 12;
  return Math.min(content, Math.max(0, viewport - sideGutter * 2));
}
