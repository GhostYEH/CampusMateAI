export function getDockScale(pointerDistance, distance = 120, baseItemSize = 36, magnification = 60) {
  if (!Number.isFinite(pointerDistance) || distance <= 0 || baseItemSize <= 0 || magnification <= 0) return 1;

  const proximity = Math.max(0, 1 - Math.abs(pointerDistance) / distance);
  return 1 + (magnification / baseItemSize - 1) * proximity;
}
