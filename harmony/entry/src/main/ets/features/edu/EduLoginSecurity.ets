import { EduCookieDto } from '../../data/EduCookieDto';

export interface EduAllowedOriginsPayload {
  allowed_origins?: string[];
}

/** Preserve the backend response allow-list; missing legacy fields remain fail-closed. */
export function allowedOriginsFromEduResponse(response: EduAllowedOriginsPayload): string[] {
  return response.allowed_origins ?? [];
}

function canonicalHttpsOrigin(value: string): string | undefined {
  const match: RegExpExecArray | null = /^https:\/\/([a-zA-Z0-9.-]+)(?::([0-9]+))?(?:[/?#]|$)/.exec(value);
  if (match === null) return undefined;
  const host: string = match[1].toLowerCase();
  const portNumber: number = match[2] === undefined ? 443 : Number.parseInt(match[2]);
  if (portNumber < 1 || portNumber > 65535) return undefined;
  return portNumber === 443 ? `https://${host}` : `https://${host}:${portNumber}`;
}

/** Only exact HTTPS login origins supplied by the backend flow are allowed. */
export function isAllowedEduNavigation(url: string, loginUrl: string, backendAllowedOrigins: string[] = []): boolean {
  const target: string | undefined = canonicalHttpsOrigin(url);
  const loginOrigin: string | undefined = canonicalHttpsOrigin(loginUrl);
  if (target === undefined || loginOrigin === undefined) return false;
  if (target === loginOrigin) return true;
  for (let index = 0; index < backendAllowedOrigins.length; index++) {
    if (target === canonicalHttpsOrigin(backendAllowedOrigins[index])) return true;
  }
  return false;
}

/** ArkWeb exposes only name/value; unavailable attributes deliberately stay undefined. */
export function cookieDtosForUrl(cookieString: string, url: string): EduCookieDto[] {
  const origin: string | undefined = canonicalHttpsOrigin(url);
  if (origin === undefined) return [];
  const domain: string = origin.slice('https://'.length).split(':')[0];
  const entries: EduCookieDto[] = [];
  const parts: string[] = cookieString.split(';');
  for (let index = 0; index < parts.length; index++) {
    const item: string = parts[index].trim();
    const separator: number = item.indexOf('=');
    if (separator <= 0) continue;
    const name: string = item.slice(0, separator).trim();
    const value: string = item.slice(separator + 1).trim();
    if (name.length > 0) entries.push({ name: name, value: value, domain: domain, source_url: url, host_only: true });
  }
  return entries;
}
