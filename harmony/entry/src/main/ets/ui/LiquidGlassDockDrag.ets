export function clampDockDragOffset(
  selectedIndex: number,
  itemCount: number,
  itemWidth: number,
  requestedOffset: number
): number {
  if (itemCount <= 0 || itemWidth <= 0) return 0;
  const safeSelectedIndex: number = Math.min(Math.max(selectedIndex, 0), itemCount - 1);
  const minimumOffset: number = -safeSelectedIndex * itemWidth;
  const maximumOffset: number = (itemCount - 1 - safeSelectedIndex) * itemWidth;
  return Math.min(Math.max(requestedOffset, minimumOffset), maximumOffset);
}

export function dockDragTargetIndex(
  selectedIndex: number,
  dragOffset: number,
  itemWidth: number,
  itemCount: number
): number {
  if (itemCount <= 0) return 0;
  const safeSelectedIndex: number = Math.min(Math.max(selectedIndex, 0), itemCount - 1);
  if (itemWidth <= 0) return safeSelectedIndex;
  return Math.min(
    Math.max(Math.round(safeSelectedIndex + dragOffset / itemWidth), 0),
    itemCount - 1
  );
}
