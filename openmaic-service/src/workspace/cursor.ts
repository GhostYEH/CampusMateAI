/**
 * Keyset cursor helpers.
 *
 * Offset pagination re-reads rows that were already shown when something is
 * inserted mid-scroll, and skips rows when something is deleted. A keyset cursor
 * names the last row seen instead, so a page boundary is stable under both.
 *
 * The cursor is opaque to the client and **validated on the way back in**: a
 * hand-crafted cursor must not be able to make the query return another user's
 * rows, so only the two sort-key parts are encoded and both are re-applied as
 * bound parameters alongside the ownership filters.
 */

export interface Cursor {
  updatedAt: string;
  id: string;
}

export function encodeCursor(cursor: Cursor): string {
  return Buffer.from(JSON.stringify([cursor.updatedAt, cursor.id]), 'utf8').toString('base64url');
}

export function decodeCursor(value: string | null | undefined): Cursor | null {
  if (!value) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(Buffer.from(value, 'base64url').toString('utf8'));
  } catch {
    return null;
  }
  if (!Array.isArray(parsed) || parsed.length !== 2) return null;
  const [updatedAt, id] = parsed;
  if (typeof updatedAt !== 'string' || typeof id !== 'string') return null;
  return { updatedAt, id };
}
