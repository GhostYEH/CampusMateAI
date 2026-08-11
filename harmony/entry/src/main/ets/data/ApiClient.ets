import { http } from '@kit.NetworkKit';

export class ApiClient {
  private readonly baseUrl: string;
  private readonly tokenProvider: () => string;

  constructor(baseUrl: string, tokenProvider: () => string) {
    this.baseUrl = baseUrl;
    this.tokenProvider = tokenProvider;
  }
  normalizedUrl(path: string): string { return `${this.baseUrl.replace(/\/$/, '')}/${path.replace(/^\//, '')}`; }
  async login(username: string, password: string): Promise<string> {
    const client = http.createHttp();
    try {
      const response = await client.request(this.normalizedUrl('auth/login'), {
        method: http.RequestMethod.POST,
        header: { 'Content-Type': 'application/json' },
        extraData: JSON.stringify({ username: username, password: password }),
        connectTimeout: 10000,
        readTimeout: 15000
      });
      if (response.responseCode !== 200) throw new Error(`登录失败 (${response.responseCode})`);
      const body: string = response.result.toString();
      const match: RegExpMatchArray | null = body.match(/"access_token"\s*:\s*"([^"]+)"/);
      if (match === null || match[1].length === 0) throw new Error('登录响应中缺少 access_token');
      return match[1];
    } finally { client.destroy(); }
  }
  async request<T>(method: http.RequestMethod, path: string, body?: object): Promise<T> {
    const client = http.createHttp();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (this.tokenProvider()) headers.Authorization = `Bearer ${this.tokenProvider()}`;
    try {
      const response = await client.request(this.normalizedUrl(path), { method, header: headers, extraData: body ? JSON.stringify(body) : undefined, connectTimeout: 10000, readTimeout: 15000 });
      if (response.responseCode < 200 || response.responseCode >= 300) throw new Error(`请求失败 (${response.responseCode})`);
      return JSON.parse(response.result.toString()) as T;
    } finally { client.destroy(); }
  }
}
