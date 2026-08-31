import { emptyGamificationSnapshot } from "./gamificationModel.js";

const STORAGE_PREFIX = "campus_gamification_v1:";

function storageKey(accountKey) {
  return `${STORAGE_PREFIX}${encodeURIComponent(String(accountKey || "anonymous"))}`;
}

function normalizeSnapshot(value) {
  if (!value || typeof value !== "object") return emptyGamificationSnapshot();
  const events = Array.isArray(value.events) ? value.events
    .filter((event) => event && typeof event.id === "string" && event.id && Number.isFinite(Number(event.xp)))
    .map((event) => ({
      id: event.id,
      xp: Math.max(0, Number(event.xp)),
      awardedAt: typeof event.awardedAt === "string" ? event.awardedAt : "",
      ...(typeof event.sourceType === "string" ? { sourceType: event.sourceType } : {}),
      ...(typeof event.sourceId === "string" ? { sourceId: event.sourceId } : {}),
    })) : [];
  const achievements = Array.isArray(value.achievements) ? value.achievements
    .filter((achievement) => achievement && typeof achievement.id === "string" && achievement.id)
    .map((achievement) => ({
      id: achievement.id,
      unlockedAt: typeof achievement.unlockedAt === "string" ? achievement.unlockedAt : "",
    })) : [];
  return { version: 1, events, achievements };
}

export function createLocalGamificationRepository(storage = globalThis.localStorage) {
  return {
    load(accountKey) {
      try {
        const raw = storage?.getItem(storageKey(accountKey));
        return raw ? normalizeSnapshot(JSON.parse(raw)) : emptyGamificationSnapshot();
      } catch {
        return emptyGamificationSnapshot();
      }
    },
    save(accountKey, snapshot) {
      const normalized = normalizeSnapshot(snapshot);
      storage?.setItem(storageKey(accountKey), JSON.stringify(normalized));
      return normalized;
    },
  };
}
