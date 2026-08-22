/**
 * QR payload 协议 — 跨端统一解析。
 *
 * 格式: campusmate://auth/web-login?v=1&sid=<session_id>&token=<scan_token>
 *
 * 不接受任意 URL，严格校验 scheme / host / path / version / 参数。
 */

export const QR_SCHEME: string = 'campusmate';
export const QR_HOST: string = 'auth';
export const QR_PATH: string = '/web-login';
export const QR_VERSION: number = 1;

export interface QrPayload {
  sessionId: string;
  scanToken: string;
  version: number;
}

/**
 * 解析并严格校验二维码字符串。
 * 返回 null 表示不是有效的 CampusMate 登录二维码。
 */
export function parseQrPayload(raw: string): QrPayload | null {
  if (!raw || raw.trim().length === 0) return null;
  const trimmed: string = raw.trim();
  const prefix: string = `${QR_SCHEME}://`;
  if (!trimmed.startsWith(prefix)) return null;
  const afterScheme: string = trimmed.substring(prefix.length);
  const queryStart: number = afterScheme.indexOf('?');
  const authorityAndPath: string = queryStart >= 0 ? afterScheme.substring(0, queryStart) : afterScheme;
  const queryString: string = queryStart >= 0 ? afterScheme.substring(queryStart + 1) : '';
  const pathStart: number = authorityAndPath.indexOf('/');
  const host: string = pathStart >= 0 ? authorityAndPath.substring(0, pathStart) : authorityAndPath;
  const path: string = pathStart >= 0 ? authorityAndPath.substring(pathStart) : '';
  if (host !== QR_HOST) return null;
  if (path !== QR_PATH) return null;
  const params: Record<string, string> = {};
  const pairs: string[] = queryString.split('&');
  for (let i = 0; i < pairs.length; i++) {
    const pair: string = pairs[i];
    const eq: number = pair.indexOf('=');
    if (eq >= 0) {
      const key: string = pair.substring(0, eq);
      const value: string = pair.substring(eq + 1);
      params[key] = value;
    }
  }
  const versionStr: string | undefined = params['v'];
  if (!versionStr) return null;
  const version: number = parseInt(versionStr, 10);
  if (isNaN(version) || version !== QR_VERSION) return null;
  const sessionId: string | undefined = params['sid'];
  const scanToken: string | undefined = params['token'];
  if (!sessionId || !scanToken) return null;
  if (sessionId.length < 16) return null;
  if (scanToken.length < 32) return null;
  return { sessionId, scanToken, version };
}