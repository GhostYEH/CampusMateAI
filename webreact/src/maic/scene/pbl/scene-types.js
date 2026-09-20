import { trimmedPBLText } from '../lib/pbl-readers.js';

/**
 * 移植自参考项目 `components/scene-renderers/pbl/v2/scene-stage/scene-types.ts`。
 * 仅擦除 TypeScript interface / 类型标注。
 *
 * PBL v2 — Scene-visual sanitization (SCENARIO ONLY, increment 5).
 *
 * The scene backdrop is driven entirely by the design-time, LLM-authored
 * `scenario.sceneVisual` (a project-wide caption + free-form palette + emoji
 * motifs that fit ALL roleplay stages). This module only SANITIZES that spec
 * into render-safe values with neutral fallbacks, so a missing / malformed
 * value (e.g. an older package with no sceneVisual) can never break the view.
 * Pure + deterministic — no enumeration, no keyword guessing, no network.
 */

/** Neutral fallback palette (used when sceneVisual is absent/invalid). */
const FALLBACK = { bg1: '#26244a', bg2: '#1a1934', accent: '#9d8cff' };

const HEX = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

function hex(value, fallback) {
  const v = trimmedPBLText(value);
  return v && HEX.test(v) ? v : fallback;
}

/** Coerce a (possibly missing/malformed) sceneVisual into render-safe values.
 *  Always returns a complete, valid object — never throws. */
export function sanitizeSceneVisual(visual) {
  const motifs = (visual?.motifs ?? [])
    .map((m) => (typeof m === 'string' ? m.trim() : ''))
    .filter((m) => m.length > 0 && m.length <= 8)
    .slice(0, 4);
  const caption = trimmedPBLText(visual?.caption);
  return {
    bg1: hex(visual?.bg1, FALLBACK.bg1),
    bg2: hex(visual?.bg2, FALLBACK.bg2),
    accent: hex(visual?.accent, FALLBACK.accent),
    motifs,
    caption: caption && caption.length > 0 ? caption.slice(0, 80) : undefined,
  };
}
