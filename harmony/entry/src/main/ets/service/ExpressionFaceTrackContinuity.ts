export interface ExpressionFaceBox {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** Conservative geometry continuity check; it is not a face identity guarantee. */
export class ExpressionFaceTrackContinuity {
  static isSameTrack(previous: ExpressionFaceBox, current: ExpressionFaceBox,
    frameWidth: number, frameHeight: number): boolean {
    if (frameWidth <= 0 || frameHeight <= 0 || previous.width <= 0 || previous.height <= 0 ||
      current.width <= 0 || current.height <= 0) return false;
    const centerXDelta: number = (previous.left + previous.width / 2 - current.left - current.width / 2) /
      frameWidth;
    const centerYDelta: number = (previous.top + previous.height / 2 - current.top - current.height / 2) /
      frameHeight;
    const centerDistance: number = Math.sqrt(centerXDelta * centerXDelta + centerYDelta * centerYDelta);
    const scaleRatio: number = Math.max(previous.width / current.width, current.width / previous.width,
      previous.height / current.height, current.height / previous.height);
    const overlap: number = ExpressionFaceTrackContinuity.iou(previous, current);
    return scaleRatio <= 1.8 && (overlap >= 0.12 || centerDistance <= 0.08);
  }

  private static iou(first: ExpressionFaceBox, second: ExpressionFaceBox): number {
    const left: number = Math.max(first.left, second.left);
    const top: number = Math.max(first.top, second.top);
    const right: number = Math.min(first.left + first.width, second.left + second.width);
    const bottom: number = Math.min(first.top + first.height, second.top + second.height);
    const intersection: number = Math.max(0, right - left) * Math.max(0, bottom - top);
    const union: number = first.width * first.height + second.width * second.height - intersection;
    return union <= 0 ? 0 : intersection / union;
  }
}
