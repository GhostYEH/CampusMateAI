const HITOKOTO_ENDPOINT = "https://v1.hitokoto.cn";
const UNKNOWN_VALUES = new Set(["", "未知", "unknown", "undefined", "null"]);
const HITOKOTO_CATEGORIES = ["d", "i", "k", "e"];
const UNSUITABLE_PATTERNS = [
  /自杀|杀人|死亡|死去|毁灭|仇恨|绝望|暴力|血腥|色情|强奸|毒品|赌博/,
  /(?:哈|呵|嘻|啊|哦|嗯|呜|233|666){3,}/i,
];

function usable(value) {
  const normalized = String(value ?? "").trim();
  return !UNKNOWN_VALUES.has(normalized.toLowerCase()) ? normalized : "";
}

export function formatHitokotoSource({ from_who: author, from: source } = {}) {
  const authorText = usable(author);
  const sourceText = usable(source);
  const parts = [authorText, sourceText].filter(Boolean);
  return parts.length ? `—— ${parts.join(" · ")}` : "—— 一言";
}

export function isSuitableHitokoto({ hitokoto: text, type } = {}) {
  const sentence = String(text ?? "").trim();
  if (sentence.length < 6 || sentence.length > 80) return false;
  if (type && !HITOKOTO_CATEGORIES.includes(type)) return false;
  return !UNSUITABLE_PATTERNS.some((pattern) => pattern.test(sentence));
}

function hitokotoUrl() {
  const params = new URLSearchParams({ min_length: "6", max_length: "80" });
  HITOKOTO_CATEGORIES.forEach((category) => params.append("c", category));
  return `${HITOKOTO_ENDPOINT}?${params.toString()}`;
}

async function fetchHitokotoOnce({ timeoutMs, fetchImpl }) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetchImpl(hitokotoUrl(), { signal: controller.signal });
    if (!response.ok) throw new Error(`Hitokoto request failed: ${response.status}`);
    const data = await response.json();
    if (!data || typeof data.uuid !== "string" || !data.uuid.trim() || typeof data.hitokoto !== "string" || !data.hitokoto.trim()) {
      throw new Error("Invalid Hitokoto response");
    }
    return { uuid: data.uuid.trim(), hitokoto: data.hitokoto.trim(), from: data.from ?? "", from_who: data.from_who ?? null, type: data.type ?? "" };
  } finally {
    clearTimeout(timeout);
  }
}

export async function fetchHitokoto({ timeoutMs = 7000, fetchImpl = globalThis.fetch, maxAttempts = 2 } = {}) {
  let lastUnsuitable = null;
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const data = await fetchHitokotoOnce({ timeoutMs, fetchImpl });
    if (isSuitableHitokoto(data)) return data;
    lastUnsuitable = new Error("Unsuitable Hitokoto response");
  }
  throw lastUnsuitable || new Error("Unsuitable Hitokoto response");
}
