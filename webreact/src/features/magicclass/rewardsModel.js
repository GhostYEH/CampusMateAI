/**
 * 课堂游戏化的纯函数层。
 *
 * 所有规则都写成不依赖 React / DOM 的函数，界面只负责展示。这样"加多少分、
 * 什么时候解锁成就"可以单独钉在测试里，而不是散落在 JSX 里靠肉眼判断。
 *
 * 三条底线：
 * 1. **不编造进度。** 没访问过的场景不算完成，没答对的题不算分。
 * 2. **重复不算分。** 同一场景首次访问、同一场景首次交卷各只结算一次，
 *    刷新或来回翻页都不会重复加 XP。
 * 3. **存储失败不影响上课。** localStorage 不可用时退化为内存态，页面照常。
 */

export const REWARD_VERSION = 1;
export const XP_PER_SCENE = 12;
export const XP_PER_CORRECT = 6;
export const XP_PERFECT_BONUS = 20;
export const XP_COMBO_BONUS = 12;
export const LEVEL_STEP = 100;

export const ACHIEVEMENTS = [
  { id: "first_scene", label: "开课了", detail: "完成第一页课堂内容", icon: "book" },
  { id: "half_route", label: "过半", detail: "完成一半以上的页面", icon: "route" },
  { id: "finish_route", label: "走完这一章", detail: "完成本章全部页面", icon: "flag" },
  { id: "combo_3", label: "三连对", detail: "连续答对三份测验", icon: "flame" },
  { id: "combo_5", label: "五连对", detail: "连续答对五份测验", icon: "bolt" },
  { id: "perfect_quiz", label: "满分答卷", detail: "一份测验全部答对", icon: "star" },
];

const ACHIEVEMENT_IDS = new Set(ACHIEVEMENTS.map((item) => item.id));

export function emptyRewards() {
  return {
    version: REWARD_VERSION,
    xp: 0,
    visited: {},
    quiz: {},
    combo: 0,
    bestCombo: 0,
    achievements: [],
    updatedAt: "",
  };
}

function numberOrZero(value) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : 0;
}

/** 把任意来源的快照收敛成合法状态；坏数据只丢坏字段，不做"整份重置"。 */
export function normalizeRewards(raw) {
  if (!raw || typeof raw !== "object") return emptyRewards();
  const visited = {};
  for (const [sceneId, value] of Object.entries(raw.visited || {})) {
    if (sceneId && value) visited[sceneId] = true;
  }
  const quiz = {};
  for (const [sceneId, value] of Object.entries(raw.quiz || {})) {
    if (!sceneId || !value || typeof value !== "object") continue;
    quiz[sceneId] = {
      correct: numberOrZero(value.correct),
      total: numberOrZero(value.total),
      perfect: Boolean(value.perfect),
    };
  }
  return {
    version: REWARD_VERSION,
    xp: numberOrZero(raw.xp),
    visited,
    quiz,
    combo: numberOrZero(raw.combo),
    bestCombo: numberOrZero(raw.bestCombo),
    achievements: Array.isArray(raw.achievements)
      ? [...new Set(raw.achievements.filter((id) => ACHIEVEMENT_IDS.has(id)))]
      : [],
    updatedAt: typeof raw.updatedAt === "string" ? raw.updatedAt : "",
  };
}

/** 等级从 1 开始，每 `LEVEL_STEP` XP 升一级；返回展示所需的全部派生值。 */
export function levelOf(xp) {
  const total = numberOrZero(xp);
  const level = Math.floor(total / LEVEL_STEP) + 1;
  const inLevel = total % LEVEL_STEP;
  return {
    level,
    xp: total,
    inLevel,
    toNext: LEVEL_STEP - inLevel,
    progress: inLevel / LEVEL_STEP,
  };
}

export function rewardsKey({ courseId, workspaceId, stageId }) {
  if (!stageId) return "";
  return `campusmate:classroom-rewards:v1:${courseId || "-"}:${workspaceId || "-"}:${stageId}`;
}

export function readRewards(storage, key) {
  if (!key || !storage) return emptyRewards();
  try {
    const raw = storage.getItem(key);
    return raw ? normalizeRewards(JSON.parse(raw)) : emptyRewards();
  } catch {
    return emptyRewards();
  }
}

/** 写入失败（隐私模式/配额满）时返回 false，调用方继续用内存态。 */
export function writeRewards(storage, key, state) {
  if (!key || !storage) return false;
  try {
    storage.setItem(key, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}

/** 依据已有状态计算应当解锁的成就；返回新增的那几个，供界面提示。 */
export function unlockedAchievements(state, { totalScenes = 0 } = {}) {
  const visitedCount = Object.keys(state.visited || {}).length;
  const quizzes = Object.values(state.quiz || {});
  const earned = new Set(state.achievements || []);
  const next = [];
  const add = (id, condition) => {
    if (condition && !earned.has(id)) next.push(id);
  };
  add("first_scene", visitedCount >= 1);
  add("half_route", totalScenes >= 2 && visitedCount >= Math.ceil(totalScenes / 2));
  add("finish_route", totalScenes > 0 && visitedCount >= totalScenes);
  add("combo_3", numberOrZero(state.bestCombo) >= 3);
  add("combo_5", numberOrZero(state.bestCombo) >= 5);
  add("perfect_quiz", quizzes.some((item) => item.perfect));
  return next;
}

function withUnlocks(state, context, awarded) {
  const next = unlockedAchievements(state, context);
  if (!next.length) return { state, unlocked: [] };
  return {
    state: { ...state, achievements: [...state.achievements, ...next], updatedAt: new Date().toISOString() },
    unlocked: next,
  };
}

/** 首次访问某场景：只结算一次 XP。 */
export function visitScene(state, sceneId, context = {}) {
  const current = normalizeRewards(state);
  if (!sceneId || current.visited[sceneId]) return { state: current, awarded: 0, unlocked: [] };
  const next = {
    ...current,
    xp: current.xp + XP_PER_SCENE,
    visited: { ...current.visited, [sceneId]: true },
  };
  const result = withUnlocks(next, context);
  return { state: result.state, awarded: XP_PER_SCENE, unlocked: result.unlocked };
}

/**
 * 第一次为某场景交卷：按答对题数结算，答对 >0 时连击 +1，答错清零。
 * 同一场景重复交卷不重复给分，也不改动连击（重做不是新战绩）。
 */
export function gradeScene(state, { sceneId, correct, total } = {}, context = {}) {
  const current = normalizeRewards(state);
  const right = Math.min(numberOrZero(correct), numberOrZero(total) || numberOrZero(correct));
  const totalQuestions = numberOrZero(total) || right;
  if (!sceneId || current.quiz[sceneId] || totalQuestions === 0) {
    return { state: current, awarded: 0, unlocked: [], combo: current.combo };
  }
  const perfect = totalQuestions > 0 && right === totalQuestions;
  const combo = right > 0 ? current.combo + 1 : 0;
  const xp = right * XP_PER_CORRECT
    + (perfect ? XP_PERFECT_BONUS : 0)
    + (right > 0 && combo > 1 ? XP_COMBO_BONUS : 0);
  const next = {
    ...current,
    xp: current.xp + xp,
    combo,
    bestCombo: Math.max(current.bestCombo, combo),
    quiz: { ...current.quiz, [sceneId]: { correct: right, total: totalQuestions, perfect } },
  };
  const result = withUnlocks(next, context);
  return { state: result.state, awarded: xp, unlocked: result.unlocked, combo };
}

/** 关卡地图：把播放计划的场景与本地的完成记录合并，缺一不可。 */
export function sceneMap(state, scenes = [], currentIndex = 0) {
  const current = normalizeRewards(state);
  return (scenes || []).map((scene, index) => ({
    id: scene.id,
    title: scene.title || `第 ${index + 1} 页`,
    type: scene.type || "unknown",
    visited: Boolean(current.visited[scene.id]),
    quizzed: Boolean(current.quiz[scene.id]),
    current: index === currentIndex,
  }));
}
