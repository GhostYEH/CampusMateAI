export interface BingDailyWallpaperResponse {
  date?: string;
  title?: string;
  image_url?: string;
  image_url_4k?: string;
  image_url_1080?: string;
}

export interface BingDailyWallpaper {
  date: string;
  title: string;
  imageUrl: string;
}

function trimmed(value: string | undefined): string {
  return value === undefined ? '' : value.trim();
}

function usableImageUrl(value: string | undefined): string {
  const url: string = trimmed(value);
  return url.startsWith('https://') || url.startsWith('http://') ? url : '';
}

function preferredImageUrl(response: BingDailyWallpaperResponse): string {
  const image1080: string = usableImageUrl(response.image_url_1080);
  if (image1080.length > 0) return image1080;
  const image: string = usableImageUrl(response.image_url);
  if (image.length > 0) return image;
  const image4k: string = usableImageUrl(response.image_url_4k);
  if (image4k.length > 0) return image4k;
  throw new Error('必应壁纸响应缺少图片地址');
}

export function parseBingDailyWallpaperResponse(raw: string): BingDailyWallpaper {
  if (raw.trim().length === 0) throw new Error('必应壁纸返回空数据');
  const response: BingDailyWallpaperResponse = JSON.parse(raw) as BingDailyWallpaperResponse;
  return {
    date: trimmed(response.date),
    title: trimmed(response.title),
    imageUrl: preferredImageUrl(response)
  };
}

export function bingDailyWallpaperImageUrl(wallpaper: BingDailyWallpaper): string {
  return wallpaper.imageUrl;
}
