import { describe, expect, it } from '@ohos/hypium';
import { bingDailyWallpaperImageUrl, parseBingDailyWallpaperResponse } from '../../../main/ets/data/BingDailyWallpaperModels';

export default function bingDailyWallpaperModelsTest(): void {
  describe('BingDailyWallpaperModels', () => {
    it('prefers the 1080p image for the home background', 0, () => {
      const wallpaper = parseBingDailyWallpaperResponse('{"image_url":"https://example.com/fallback.jpg","image_url_1080":"https://example.com/1080.jpg","image_url_4k":"https://example.com/4k.jpg"}');

      expect(bingDailyWallpaperImageUrl(wallpaper)).assertEqual('https://example.com/1080.jpg');
    });

    it('falls back when the preferred image is missing', 0, () => {
      const wallpaper = parseBingDailyWallpaperResponse('{"image_url":"https://example.com/fallback.jpg"}');

      expect(bingDailyWallpaperImageUrl(wallpaper)).assertEqual('https://example.com/fallback.jpg');
    });

    it('rejects a response without a usable image', 0, () => {
      let failed: boolean = false;
      try {
        parseBingDailyWallpaperResponse('{"image_url_1080":" "}');
      } catch (_) {
        failed = true;
      }

      expect(failed).assertTrue();
    });

    it('rejects non-http image sources', 0, () => {
      let failed: boolean = false;
      try {
        parseBingDailyWallpaperResponse('{"image_url_1080":"file:///secret.jpg"}');
      } catch (_) {
        failed = true;
      }

      expect(failed).assertTrue();
    });
  });
}
