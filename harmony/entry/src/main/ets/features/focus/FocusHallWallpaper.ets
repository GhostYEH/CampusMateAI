export type FocusHallWallpaperId =
  'MISTY_FOREST' |
  'ALPINE_LAKE' |
  'BAMBOO_STREAM' |
  'COASTAL_TWILIGHT' |
  'RAINWASHED_MEADOW';

export const FOCUS_HALL_WALLPAPERS: FocusHallWallpaperId[] = [
  'MISTY_FOREST',
  'ALPINE_LAKE',
  'BAMBOO_STREAM',
  'COASTAL_TWILIGHT',
  'RAINWASHED_MEADOW'
];

export function chooseFocusHallWallpaper(
  previous: FocusHallWallpaperId | undefined,
  randomIndex: number
): FocusHallWallpaperId {
  const candidates: FocusHallWallpaperId[] = previous === undefined
    ? FOCUS_HALL_WALLPAPERS
    : FOCUS_HALL_WALLPAPERS.filter(
      (wallpaper: FocusHallWallpaperId): boolean => wallpaper !== previous
    );
  const index: number = ((Math.trunc(randomIndex) % candidates.length) + candidates.length) % candidates.length;
  return candidates[index];
}

export class FocusHallWallpaperPicker {
  private static previous: FocusHallWallpaperId | undefined = undefined;

  static next(): FocusHallWallpaperId {
    const selected: FocusHallWallpaperId = chooseFocusHallWallpaper(
      FocusHallWallpaperPicker.previous,
      Math.floor(Math.random() * 2147483647)
    );
    FocusHallWallpaperPicker.previous = selected;
    return selected;
  }
}
