const SNAPSHOT_VERSION = 1;

export const ACHIEVEMENT_DEFINITIONS = Object.freeze([
  { id: "first-focus", title: "初心者", description: "完成第一次专注", icon: "PhSparkle" },
  { id: "focus-60", title: "专注起航", description: "累计专注 60 分钟", icon: "PhTimer" },
  { id: "focus-600", title: "学习达人", description: "累计专注 10 小时", icon: "PhBookOpenText" },
  { id: "task-hunter-50", title: "任务猎人", description: "完成 50 个个人待办", icon: "PhTarget" },
  { id: "streak-7", title: "坚持不懈", description: "连续学习 7 天", icon: "PhFire" },
]);

export function emptyGamificationSnapshot() {
  return { version: SNAPSHOT_VERSION, events: [], achievements: [] };
}

export function calculateLevel(value) {
  const totalXp = Math.max(0, Math.floor(Number(value) || 0));
  let level = 1;
  let currentLevelXp = totalXp;
  let nextLevelXp = 100;

  while (currentLevelXp >= nextLevelXp) {
    currentLevelXp -= nextLevelXp;
    level += 1;
    nextLevelXp = 100 + 25 * (level - 1);
  }

  return {
    level,
    totalXp,
    currentLevelXp,
    nextLevelXp,
    progress: nextLevelXp ? currentLevelXp / nextLevelXp : 0,
  };
}

export function localDateKey(value) {
  if (typeof value === "string") {
    const dateOnly = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (dateOnly) {
      const [, year, month, day] = dateOnly;
      const parsed = new Date(Number(year), Number(month) - 1, Number(day), 12);
      if (parsed.getFullYear() === Number(year)
        && parsed.getMonth() === Number(month) - 1
        && parsed.getDate() === Number(day)) return value;
      return null;
    }
  }
  const parsed = value instanceof Date ? new Date(value) : new Date(value);
  if (Number.isNaN(parsed.valueOf())) return null;
  return [
    parsed.getFullYear(),
    String(parsed.getMonth() + 1).padStart(2, "0"),
    String(parsed.getDate()).padStart(2, "0"),
  ].join("-");
}

function addLocalDays(dateKey, amount) {
  const [year, month, day] = dateKey.split("-").map(Number);
  const date = new Date(year, month - 1, day, 12);
  date.setDate(date.getDate() + amount);
  return localDateKey(date);
}

export function calculateStreak(activityDates, now = new Date()) {
  const dates = new Set((activityDates || []).map(localDateKey).filter(Boolean));
  const today = localDateKey(now);
  if (!today || dates.size === 0) return 0;

  let cursor = dates.has(today) ? today : addLocalDays(today, -1);
  let streak = 0;
  while (cursor && dates.has(cursor)) {
    streak += 1;
    cursor = addLocalDays(cursor, -1);
  }
  return streak;
}

function completedTasks(facts) {
  return (facts?.completedTasks || []).filter((task) => task?.id && task.status === "completed" && localDateKey(task.completed_at));
}

function completedFocusSessions(facts) {
  return (facts?.completedFocusSessions || []).filter((session) => (
    session?.id
    && session.status === "completed"
    && session.mode === "focus"
    && localDateKey(session.ended_at || session.started_at)
  ));
}

export function activityDatesFromFacts(facts) {
  return [
    ...completedTasks(facts).map((task) => task.completed_at),
    ...completedFocusSessions(facts).map((session) => session.ended_at || session.started_at),
  ];
}

function taskXp(task) {
  return ["urgent", "high"].includes(String(task.importance || task.priority || "").toLowerCase()) ? 30 : 20;
}

function createEvent(id, xp, awardedAt, sourceType, sourceId) {
  return { id, xp, awardedAt: awardedAt || "", sourceType, sourceId };
}

export function reconcileXpEvents(snapshot, facts, now = new Date()) {
  const previous = snapshot || emptyGamificationSnapshot();
  const events = Array.isArray(previous.events) ? [...previous.events] : [];
  const knownIds = new Set(events.map((event) => event.id));
  const tasks = completedTasks(facts);
  const focusSessions = completedFocusSessions(facts);

  const append = (event) => {
    if (!knownIds.has(event.id)) {
      events.push(event);
      knownIds.add(event.id);
    }
  };

  tasks.forEach((task) => append(createEvent(
    `TASK_COMPLETED:${task.id}`,
    taskXp(task),
    task.completed_at,
    "TASK_COMPLETED",
    String(task.id),
  )));

  focusSessions
    .filter((session) => Number(session.duration_seconds || 0) >= 25 * 60)
    .forEach((session) => append(createEvent(
      `FOCUS_SESSION_COMPLETED:${session.id}`,
      15,
      session.ended_at || session.started_at,
      "FOCUS_SESSION_COMPLETED",
      String(session.id),
    )));

  const today = localDateKey(now);
  const todayTasks = tasks.filter((task) => localDateKey(task.completed_at) === today);
  if (today && todayTasks.length > 0) {
    append(createEvent(`DAILY_TASK_GOAL:${today}`, 20, now.toISOString(), "DAILY_TASK_GOAL", today));
  }

  const todayFocusSeconds = focusSessions
    .filter((session) => localDateKey(session.ended_at || session.started_at) === today)
    .reduce((sum, session) => sum + Math.max(0, Number(session.duration_seconds || 0)), 0);
  if (today && todayFocusSeconds >= 60 * 60) {
    append(createEvent(`DAILY_FOCUS_GOAL:${today}`, 30, now.toISOString(), "DAILY_FOCUS_GOAL", today));
  }

  return {
    version: SNAPSHOT_VERSION,
    events,
    achievements: Array.isArray(previous.achievements) ? [...previous.achievements] : [],
    totalXp: events.reduce((sum, event) => sum + Math.max(0, Number(event.xp || 0)), 0),
  };
}

export function evaluateAchievements(snapshot, facts, now = new Date()) {
  const previous = snapshot || emptyGamificationSnapshot();
  const achievements = Array.isArray(previous.achievements) ? [...previous.achievements] : [];
  const unlocked = new Set(achievements.map((achievement) => achievement.id));
  const tasks = completedTasks(facts);
  const focusSessions = completedFocusSessions(facts);
  const focusMinutes = focusSessions.reduce(
    (sum, session) => sum + Math.max(0, Number(session.duration_seconds || 0)) / 60,
    0,
  );
  const streak = calculateStreak(activityDatesFromFacts(facts), now);
  const qualification = {
    "first-focus": focusSessions.length >= 1,
    "focus-60": focusMinutes >= 60,
    "focus-600": focusMinutes >= 600,
    "task-hunter-50": tasks.length >= 50,
    "streak-7": streak >= 7,
  };

  ACHIEVEMENT_DEFINITIONS.forEach((definition) => {
    if (qualification[definition.id] && !unlocked.has(definition.id)) {
      achievements.push({ id: definition.id, unlockedAt: now.toISOString() });
      unlocked.add(definition.id);
    }
  });

  return {
    version: SNAPSHOT_VERSION,
    events: Array.isArray(previous.events) ? [...previous.events] : [],
    achievements,
  };
}

function currentWeekBounds(now) {
  const end = new Date(now);
  const start = new Date(now);
  const mondayOffset = (start.getDay() + 6) % 7;
  start.setHours(0, 0, 0, 0);
  start.setDate(start.getDate() - mondayOffset);
  return { start: start.getTime(), end: end.getTime() };
}

function isWithin(value, bounds) {
  const at = new Date(value).getTime();
  return Number.isFinite(at) && at >= bounds.start && at <= bounds.end;
}

function titleForLevel(level) {
  if (level >= 20) return "校园领航者";
  if (level >= 10) return "成长先锋";
  if (level >= 5) return "校园探索者";
  return "校园新旅人";
}

export function summarizeGamification(snapshot, facts, now = new Date()) {
  const events = Array.isArray(snapshot?.events) ? snapshot.events : [];
  const achievements = Array.isArray(snapshot?.achievements) ? snapshot.achievements : [];
  const tasks = completedTasks(facts);
  const focusSessions = completedFocusSessions(facts);
  const today = localDateKey(now);
  const bounds = currentWeekBounds(now);
  const totalXp = events.reduce((sum, event) => sum + Math.max(0, Number(event.xp || 0)), 0);
  const level = calculateLevel(totalXp);
  const todayTasks = tasks.filter((task) => localDateKey(task.completed_at) === today);
  const todayFocusSeconds = focusSessions
    .filter((session) => localDateKey(session.ended_at || session.started_at) === today)
    .reduce((sum, session) => sum + Math.max(0, Number(session.duration_seconds || 0)), 0);

  const definitions = new Map(ACHIEVEMENT_DEFINITIONS.map((definition) => [definition.id, definition]));
  const recentAchievements = achievements
    .map((achievement) => ({ ...definitions.get(achievement.id), ...achievement }))
    .filter((achievement) => achievement.title)
    .sort((left, right) => new Date(right.unlockedAt || 0) - new Date(left.unlockedAt || 0))
    .slice(0, 3);

  return {
    ...level,
    title: titleForLevel(level.level),
    streak: calculateStreak(activityDatesFromFacts(facts), now),
    weekXp: events.filter((event) => isWithin(event.awardedAt, bounds)).reduce((sum, event) => sum + Math.max(0, Number(event.xp || 0)), 0),
    weekFocusMinutes: Math.round(focusSessions
      .filter((session) => isWithin(session.ended_at || session.started_at, bounds))
      .reduce((sum, session) => sum + Math.max(0, Number(session.duration_seconds || 0)), 0) / 60),
    weekCompletedTasks: tasks.filter((task) => isWithin(task.completed_at, bounds)).length,
    dailyAdventure: {
      completed: Number(todayTasks.length > 0) + Number(todayFocusSeconds >= 60 * 60),
      total: 2,
      focusMinutes: Math.floor(todayFocusSeconds / 60),
      completedTasks: todayTasks.length,
    },
    recentAchievements,
  };
}
