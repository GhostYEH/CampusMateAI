export const TYPING_CURSOR = "▏";

export function getTypingFrame(text, visibleCharacters, showCursor = true) {
  const characters = Array.from(String(text ?? ""));
  const count = Number.isFinite(visibleCharacters)
    ? Math.max(0, Math.min(characters.length, Math.floor(visibleCharacters)))
    : 0;
  const frame = characters.slice(0, count).join("");
  return showCursor ? `${frame}${TYPING_CURSOR}` : frame;
}

export function getTypingDelay(mean = 70, standardDeviation = 25, random = Math.random) {
  const safeMean = Number.isFinite(mean) ? Math.max(1, mean) : 70;
  const safeDeviation = Number.isFinite(standardDeviation) ? Math.max(0, standardDeviation) : 25;
  if (safeDeviation === 0) return Math.round(safeMean);

  const first = Math.min(1 - Number.EPSILON, Math.max(Number.EPSILON, random()));
  const second = Math.min(1 - Number.EPSILON, Math.max(Number.EPSILON, random()));
  const gaussian = Math.sqrt(-2 * Math.log(first)) * Math.cos(2 * Math.PI * second);
  return Math.max(16, Math.round(safeMean + gaussian * safeDeviation));
}
