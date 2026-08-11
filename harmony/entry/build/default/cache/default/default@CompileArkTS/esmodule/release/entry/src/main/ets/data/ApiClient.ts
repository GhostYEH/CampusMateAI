import http from "@ohos:net.http";
export class ApiClient {
    private readonly baseUrl: string;
    private readonly tokenProvider: () => string;
    constructor(o: string, p: () => string) {
        this.baseUrl = o;
        this.tokenProvider = p;
    }
    normalizedUrl(n: string): string { return `${this.baseUrl.replace(/\/$/, '')}/${n.replace(/^\//, '')}`; }
    async login(h: string, i: string): Promise<string> {
        const j = http.createHttp();
        try {
            const k = await j.request(this.normalizedUrl('auth/login'), {
                method: http.RequestMethod.POST,
                header: { 'Content-Type': 'application/json' },
                extraData: JSON.stringify({ username: h, password: i }),
                connectTimeout: 10000,
                readTimeout: 15000
            });
            if (k.responseCode !== 200)
                throw new Error(`登录失败 (${k.responseCode})`);
            const l: string = k.result.toString();
            const m: RegExpMatchArray | null = l.match(/"access_token"\s*:\s*"([^"]+)"/);
            if (m === null || m[1].length === 0)
                throw new Error('登录响应中缺少 access_token');
            return m[1];
        }
        finally {
            j.destroy();
        }
    }
    async request<a>(b: http.RequestMethod, c: string, d?: object): Promise<a> {
        const e = http.createHttp();
        const f: Record<string, string> = { 'Content-Type': 'application/json' };
        if (this.tokenProvider())
            f.Authorization = `Bearer ${this.tokenProvider()}`;
        try {
            const g = await e.request(this.normalizedUrl(c), { method: b, header: f, extraData: d ? JSON.stringify(d) : undefined, connectTimeout: 10000, readTimeout: 15000 });
            if (g.responseCode < 200 || g.responseCode >= 300)
                throw new Error(`请求失败 (${g.responseCode})`);
            return JSON.parse(g.result.toString()) as a;
        }
        finally {
            e.destroy();
        }
    }
}
