export enum MotionDuration {
  INSTANT = 80,
  PRESS = 150,
  STATE = 220,
  TAB = 260,
  PAGE = 300
}

export class MotionSpec {
  static duration(reduceMotion: boolean, value: MotionDuration): number {
    return reduceMotion ? 0 : value;
  }

  static fadeDuration(reduceMotion: boolean, value: MotionDuration): number {
    return reduceMotion ? MotionDuration.INSTANT : value;
  }

  static distance(reduceMotion: boolean, value: number): number {
    return reduceMotion ? 0 : value;
  }

  static scale(reduceMotion: boolean, value: number): number {
    return reduceMotion ? 1 : value;
  }

  static stagger(reduceMotion: boolean, index: number): number {
    if (reduceMotion) {
      return 0;
    }
    return Math.min(Math.max(index, 0), 3) * 35;
  }

  static glowOpacity(reduceMotion: boolean, phase: number): number {
    if (reduceMotion) {
      return 0.62;
    }
    return phase === 1 ? 0.86 : 0.56;
  }

  static glowBlur(reduceMotion: boolean): number {
    return reduceMotion ? 0 : 12;
  }
}
