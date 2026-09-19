/**
 * Sanitization for inbound DSL values.
 *
 * The rule this module enforces: **nothing from a client reaches storage or the
 * renderer in a form that can act on its own.** Two concrete surfaces need it —
 * the free-text fields (titles, prompts, personas) that end up in the DOM, and
 * the inline `html` of an `interactive` scene, which is the only place a
 * document legitimately carries executable markup.
 *
 * Inline HTML is *not* stripped of scripts: an interactive scene without scripts
 * is not interactive. It is instead (a) bounded, (b) stripped of the constructs
 * that let a document navigate or re-base the frame it runs in, and (c) always
 * rendered by the client inside a minimal-sandbox iframe. Those three together
 * are the containment story; no single one is sufficient.
 */

import { DSL_LIMITS, byteLength } from './limits.ts';

/** C0/C1 controls except tab, line feed and carriage return. */
const CONTROL_CHARS = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F]/g;

/**
 * Collapse control characters and cap length.
 *
 * Deliberately does NOT escape HTML entities: escaping here would double-escape
 * text that React already escapes on render, and would corrupt legitimate
 * content like `a < b` in a quiz question.
 */
export function sanitizeText(value: string, maxLength: number = DSL_LIMITS.maxStringLength): string {
  const cleaned = value.replace(CONTROL_CHARS, '');
  return cleaned.length > maxLength ? cleaned.slice(0, maxLength) : cleaned;
}

const ALLOWED_URL_PROTOCOLS = new Set(['http:', 'https:']);

/**
 * Accept only absolute http(s) URLs without embedded credentials.
 *
 * `javascript:`, `data:`, `file:` and `blob:` are rejected outright: a
 * document-supplied URL is rendered as an iframe `src` or an `<a href>`, and all
 * four schemes have been used to escape exactly those contexts.
 */
export function sanitizeUrl(value: string): string | null {
  let parsed: URL;
  try {
    parsed = new URL(value.trim());
  } catch {
    return null;
  }
  if (!ALLOWED_URL_PROTOCOLS.has(parsed.protocol)) return null;
  if (parsed.username || parsed.password) return null;
  return parsed.toString();
}

/** `<meta http-equiv="refresh">` — a document-supplied navigation escape. */
const META_REFRESH = /<meta\b[^>]*http-equiv\s*=\s*["']?refresh["']?[^>]*>/gi;
/** `<base href>` — re-bases every relative URL in the frame. */
const BASE_TAG = /<base\b[^>]*>/gi;

/**
 * Bound and de-fang an interactive scene's inline HTML.
 *
 * Returns `null` when the payload exceeds {@link DSL_LIMITS.maxInlineHtmlBytes},
 * so the caller rejects the document instead of persisting a payload the player
 * will refuse to load.
 */
export function sanitizeInteractiveHtml(html: string): string | null {
  const cleaned = html.replace(CONTROL_CHARS, '');
  if (byteLength(cleaned) > DSL_LIMITS.maxInlineHtmlBytes) return null;
  return cleaned.replace(META_REFRESH, '').replace(BASE_TAG, '');
}

/**
 * Recursively sanitize every string in a value, leaving the structure intact.
 *
 * Used for the free-text fields of a document (titles, descriptions, prompts).
 * Keys are preserved verbatim — renaming a key would silently change the
 * document's meaning.
 */
export function sanitizeStrings<T>(value: T, maxLength: number = DSL_LIMITS.maxStringLength): T {
  if (typeof value === 'string') return sanitizeText(value, maxLength) as unknown as T;
  if (Array.isArray(value)) return value.map((item) => sanitizeStrings(item, maxLength)) as unknown as T;
  if (typeof value === 'object' && value !== null) {
    const out: Record<string, unknown> = {};
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      out[key] = sanitizeStrings(item, maxLength);
    }
    return out as unknown as T;
  }
  return value;
}
