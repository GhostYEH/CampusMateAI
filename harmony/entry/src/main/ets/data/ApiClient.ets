import { http } from '@kit.NetworkKit';

const ENABLE_API_LOG: boolean = false;

function apiLog(message: string): void {
  if (ENABLE_API_LOG) console.log(`[API] ${message}`);
}

function safeParse<T>(raw: string): T {
  if (!raw || raw.length === 0) {
    throw new Error('服务器返回空数据');
  }
  try {
    return JSON.parse(raw) as T;
  } catch (e) {
    throw new Error('服务器返回数据格式错误');
  }
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly tokenProvider: () => string;

  constructor(baseUrl: string, tokenProvider: () => string) {
    this.baseUrl = baseUrl;
    this.tokenProvider = tokenProvider;
  }

  normalizedUrl(path: string): string { return `${this.baseUrl.replace(/\/$/, '')}/${path.replace(/^\//, '')}`; }

  private getErrorMessage(statusCode: number): string {
    switch (statusCode) {
      case 401: return '登录已过期，请重新登录';
      case 403: return '没有访问权限';
      case 404: return '请求的服务不存在';
      case 422: return '请求数据格式错误';
      case 429: return '请求过于频繁，请稍后再试';
      case 500: return '服务器内部错误，请稍后再试';
      case 502: return '网关错误，请稍后再试';
      case 503: return '服务暂时不可用';
      case 504: return '请求超时，请检查网络';
      default: return `请求失败 (${statusCode})`;
    }
  }

  private buildHeaders(): Record<string, string> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    const token: string = this.tokenProvider();
    if (token && token.length > 0) {
      headers.Authorization = `Bearer ${token}`;
    }
    return headers;
  }

  async login(username: string, password: string): Promise<string> {
    const client = http.createHttp();
    const url: string = this.normalizedUrl('auth/login');
    apiLog(`POST ${url}`);
    try {
      const response = await client.request(url, {
        method: http.RequestMethod.POST,
        header: { 'Content-Type': 'application/json' },
        extraData: JSON.stringify({ username: username, password: password }),
        connectTimeout: 10000,
        readTimeout: 15000
      });
      apiLog(`status=${response.responseCode}`);
      if (response.responseCode !== 200) {
        throw new Error(this.getErrorMessage(response.responseCode));
      }
      const data: Record<string, string> = safeParse<Record<string, string>>(response.result.toString());
      const accessToken: string | undefined = data.access_token;
      if (!accessToken || accessToken.length === 0) throw new Error('登录响应中缺少 access_token');
      return accessToken;
    } catch (e) {
      if (e instanceof Error) throw e;
      throw new Error('网络连接失败，请检查网络后重试');
    } finally { client.destroy(); }
  }

  async request<T>(method: http.RequestMethod, path: string, body?: object): Promise<T> {
    const client = http.createHttp();
    const url: string = this.normalizedUrl(path);
    apiLog(`${http.RequestMethod[method]} ${url}`);
    try {
      const response = await client.request(url, {
        method: method,
        header: this.buildHeaders(),
        extraData: body ? JSON.stringify(body) : undefined,
        connectTimeout: 10000,
        readTimeout: 15000
      });
      apiLog(`status=${response.responseCode}`);
      if (response.responseCode === 401) {
        throw new Error('登录已过期，请重新登录');
      }
      if (response.responseCode < 200 || response.responseCode >= 300) {
        throw new Error(this.getErrorMessage(response.responseCode));
      }
      return safeParse<T>(response.result.toString());
    } catch (e) {
      if (e instanceof Error) throw e;
      throw new Error('网络连接失败，请检查网络后重试');
    } finally { client.destroy(); }
  }

  async patch<T>(path: string, body: object): Promise<T> {
    return this.request<T>('PATCH' as http.RequestMethod, path, body);
  }
}
