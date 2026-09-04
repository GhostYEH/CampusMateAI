import { describe, expect, it } from '@ohos/hypium';
import {
  FOCUS_HALL_WALLPAPERS,
  FocusHallWallpaperId,
  chooseFocusHallWallpaper
} from '../../../main/ets/features/focus/FocusHallWallpaper';

export default function focusHallWallpaperTest(): void {
  describe('FocusHallWallpaper', () => {
    it('keeps the same five natural scenes as Android', 0, () => {
      expect(FOCUS_HALL_WALLPAPERS.length).assertEqual(5);
      const unique: FocusHallWallpaperId[] = FOCUS_HALL_WALLPAPERS.filter(
        (wallpaper: FocusHallWallpaperId, index: number, all: FocusHallWallpaperId[]): boolean => all.indexOf(wallpaper) === index
      );
      expect(unique.length).assertEqual(5);
    });

    it('does not immediately repeat the previous wallpaper', 0, () => {
      FOCUS_HALL_WALLPAPERS.forEach((previous: FocusHallWallpaperId) => {
        for (let index: number = 0; index < 20; index += 1) {
          const next: FocusHallWallpaperId = chooseFocusHallWallpaper(previous, index);
          expect(next === previous).assertFalse();
          expect(FOCUS_HALL_WALLPAPERS.includes(next)).assertTrue();
        }
      });
    });

    it('can select every wallpaper on first entry', 0, () => {
      const selected: FocusHallWallpaperId[] = FOCUS_HALL_WALLPAPERS.map(
        (_wallpaper: FocusHallWallpaperId, index: number): FocusHallWallpaperId => chooseFocusHallWallpaper(undefined, index)
      );
      const unique: FocusHallWallpaperId[] = selected.filter(
        (wallpaper: FocusHallWallpaperId, index: number, all: FocusHallWallpaperId[]): boolean => all.indexOf(wallpaper) === index
      );
      expect(unique.length).assertEqual(5);
    });
  });
}
