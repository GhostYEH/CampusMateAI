import { http } from '@kit.NetworkKit';
import { BingDailyWallpaper, parseBingDailyWallpaperResponse } from './BingDailyWallpaperModels';

export class BingDailyWallpaperClient {
  private readonly url: string = 'https://uapis.cn/api/v1/image/bing-daily?resolution=1080&format=json';

  async fetch(): Promise<BingDailyWallpaper> {
    const client = http.createHttp();
    try {
      const response = await client.request(this.url, {
        method: http.RequestMethod.GET,
        header: { Accept: 'application/json' },
        connectTimeout: 8000,
        readTimeout: 8000
      });
      if (response.responseCode < 200 || response.responseCode >= 300) {
        throw new Error(`必应壁纸请求失败 (${response.responseCode})`);
      }
      return parseBingDailyWallpaperResponse(response.result.toString());
    } catch (error) {
      if (error instanceof Error) throw error;
      throw new Error('必应壁纸网络连接失败');
    } finally {
      client.destroy();
    }
  }
}
