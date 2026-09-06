import { http } from '@kit.NetworkKit';
import { HitokotoQuote, parseHitokotoResponse } from './HitokotoModels';

export class HitokotoClient {
  private readonly url: string = 'https://v1.hitokoto.cn/?encode=json';

  async fetch(): Promise<HitokotoQuote> {
    const client = http.createHttp();
    try {
      const response = await client.request(this.url, {
        method: http.RequestMethod.GET,
        header: { Accept: 'application/json' },
        connectTimeout: 8000,
        readTimeout: 8000
      });
      if (response.responseCode < 200 || response.responseCode >= 300) {
        throw new Error(`一言请求失败 (${response.responseCode})`);
      }
      return parseHitokotoResponse(response.result.toString());
    } catch (error) {
      if (error instanceof Error) throw error;
      throw new Error('一言网络连接失败');
    } finally {
      client.destroy();
    }
  }
}
