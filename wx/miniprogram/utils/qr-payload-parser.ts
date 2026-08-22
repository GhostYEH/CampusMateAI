/**
 * QR payload 协议 — 跨端统一生成与解析。
 *
 * 二维码内容格式:
 *   campusmate://auth/web-login?v=1&sid=<session_id>&token=<scan_token>
 *
 * 安全:
 * - 二维码只包含随机一次性凭据(session_id + scan_token)，不含 JWT / userId / 密码。
 * - browser_token 不写入二维码。
 * - 解析时严格校验 scheme / host / version / 参数格式，拒绝任意 URL。
 */

export const QR_PAYLOAD_SCHEME = 'campusmate'
export const QR_PAYLOAD_HOST = 'auth'
export const QR_PAYLOAD_PATH = '/web-login'
export const QR_PAYLOAD_VERSION = 1

export interface QrPayload {
  sessionId: string
  scanToken: string
  version: number
}

export function buildQrPayload(sessionId: string, scanToken: string): string {
  const params = `v=${QR_PAYLOAD_VERSION}&sid=${encodeURIComponent(sessionId)}&token=${encodeURIComponent(scanToken)}`
  return `${QR_PAYLOAD_SCHEME}://${QR_PAYLOAD_HOST}${QR_PAYLOAD_PATH}?${params}`
}

/**
 * 解析并严格校验二维码字符串。
 * 返回 null 表示不是有效的 CampusMate 登录二维码，不抛异常。
 */
export function parseQrPayload(raw: string | null | undefined): QrPayload | null {
  if (!raw || typeof raw !== 'string') return null
  const text = raw.trim()
  if (!text.startsWith(`${QR_PAYLOAD_SCHEME}://`)) return null

  const schemeEnd = text.indexOf('://')
  if (schemeEnd < 0) return null
  const afterScheme = text.slice(schemeEnd + 3)
  const pathStart = afterScheme.indexOf('/')
  if (pathStart < 0) return null

  const netloc = afterScheme.slice(0, pathStart)
  if (netloc !== QR_PAYLOAD_HOST) return null

  const afterHost = afterScheme.slice(pathStart)
  const queryStart = afterHost.indexOf('?')
  const pathPart = queryStart >= 0 ? afterHost.slice(0, queryStart) : afterHost
  if (pathPart !== QR_PAYLOAD_PATH) return null
  if (queryStart < 0) return null

  const queryStr = afterHost.slice(queryStart + 1)
  const params = parseQueryString(queryStr)
  const versionRaw = params['v']
  const sid = params['sid']
  const token = params['token']
  if (!versionRaw || !sid || !token) return null

  const version = Number(versionRaw)
  if (!Number.isInteger(version) || version !== QR_PAYLOAD_VERSION) return null
  if (sid.length < 16 || token.length < 32) return null

  return { sessionId: sid, scanToken: token, version }
}

function parseQueryString(q: string): Record<string, string> {
  const result: Record<string, string> = {}
  if (!q) return result
  for (const pair of q.split('&')) {
    if (!pair) continue
    const eq = pair.indexOf('=')
    if (eq < 0) {
      result[decodeURIComponent(pair)] = ''
      continue
    }
    const key = decodeURIComponent(pair.slice(0, eq))
    const value = decodeURIComponent(pair.slice(eq + 1))
    if (!(key in result)) result[key] = value
  }
  return result
}