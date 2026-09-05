import { selectUpcomingExam, todayScheduleItems } from "./dashboardModel.js";

const HOUR_MS = 60 * 60 * 1000;
const DAY_MS = 24 * HOUR_MS;

function parsedTime(value) {
  const result = new Date(value).getTime();
  return Number.isNaN(result) ? Number.POSITIVE_INFINITY : result;
}

function sameLocalDate(value, now) {
  const date = new Date(value);
  return !Number.isNaN(date.getTime())
    && date.getFullYear() === now.getFullYear()
    && date.getMonth() === now.getMonth()
    && date.getDate() === now.getDate();
}

function examTime(exam) {
  if (!exam?.exam_date) return Number.POSITIVE_INFINITY;
  return parsedTime(`${exam.exam_date}T${exam.start_time || exam.end_time || "23:59"}`);
}

function formatMonthDay(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "暂无安排";
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}

function formatDeadline(value, now) {
  const at = parsedTime(value);
  if (!Number.isFinite(at)) return "截止时间待确认";
  const hours = Math.ceil((at - now.getTime()) / HOUR_MS);
  if (hours < 0) return `已逾期 ${Math.max(1, Math.abs(hours))} 小时`;
  if (hours === 0) return "一小时内截止";
  return `${hours} 小时后截止`;
}

function todayFocusMinutes(sessions, now) {
  const seconds = (sessions || [])
    .filter((session) => sameLocalDate(session.started_at, now))
    .reduce((total, session) => {
      if (session.status === "active") {
        const startedAt = parsedTime(session.started_at);
        if (!Number.isFinite(startedAt)) return total;
        return total + Math.max(0, Math.floor((now.getTime() - startedAt) / 1000) - Number(session.pause_seconds || 0));
      }
      return total + Math.max(0, Number(session.duration_seconds || 0));
    }, 0);
  return Math.round(seconds / 60);
}

function counselorPath(prompt) {
  return `/counselor?prompt=${encodeURIComponent(prompt)}`;
}

function buildPulse(input, now, nextExam) {
  const courses = todayScheduleItems(input.scheduleItems || [], now);
  const pendingCount = Math.max(0, Number(input.overviewMetrics?.pendingCount || 0));
  const focusMinutes = todayFocusMinutes(input.studySessions, now);
  return [
    { key: "course", label: "今日课程", value: `${courses.length} 门`, detail: courses[0]?.course_name || "今天没有排课", icon: "PhBookOpen", path: "/courses" },
    { key: "task", label: "待处理", value: `${pendingCount} 项`, detail: pendingCount ? "作业与个人待办" : "当前没有待办", icon: "PhCheckSquare", path: "/tasks" },
    { key: "exam", label: "下一场考试", value: nextExam ? formatMonthDay(nextExam.exam_date) : "暂无安排", detail: nextExam?.course_name || "尚未同步考试", icon: "PhExam", path: "/exams" },
    { key: "focus", label: "今日专注", value: `${focusMinutes} 分钟`, detail: focusMinutes ? "已记录学习时间" : "还未开始专注", icon: "PhTimer", path: "/study" },
  ];
}

function buildCommand(priority, content, input, now, nextExam) {
  return {
    priority,
    ...content,
    nextExam,
    pulse: buildPulse(input, now, nextExam),
  };
}

export function resolveHomeLearningCommand(input = {}, now = new Date()) {
  const validNow = Number.isNaN(now.getTime()) ? new Date() : now;
  const nextExam = selectUpcomingExam(input.exams || [], validNow);
  const urgent = [...(input.dueItems || [])]
    .map((item) => ({ item, at: parsedTime(item.due) }))
    .filter(({ at }) => Number.isFinite(at) && at - validNow.getTime() <= DAY_MS)
    .sort((left, right) => left.at - right.at)[0]?.item;

  if (urgent) {
    return buildCommand("deadline", {
      eyebrow: "基于当前任务与截止时间",
      headline: `先完成：${urgent.title || "临近截止事项"}`,
      detail: `${formatDeadline(urgent.due, validNow)}。先完成最接近截止的事项，再安排后续学习。`,
      primaryAction: { label: "立即处理", icon: "PhArrowRight", path: urgent.route || "/tasks" },
      secondaryAction: { label: "让 AI 帮我拆解", icon: "PhSparkle", path: counselorPath(`帮我拆解任务：${urgent.title || "临近截止事项"}`) },
    }, input, validNow, nextExam);
  }

  const nextCourse = todayScheduleItems(input.scheduleItems || [], validNow)[0];
  if (nextCourse) {
    const courseName = nextCourse.course_name || "今日课程";
    const courseMeta = [nextCourse.start_section ? `第 ${nextCourse.start_section}${nextCourse.end_section && nextCourse.end_section !== nextCourse.start_section ? `-${nextCourse.end_section}` : ""} 节` : "时间待确认", nextCourse.location].filter(Boolean).join(" · ");
    return buildCommand("course", {
      eyebrow: "基于今日课表",
      headline: `今天先跟上：${courseName}`,
      detail: `${courseMeta}。先确认课程安排，再把课后任务接入学习计划。`,
      primaryAction: { label: "查看课程", icon: "PhArrowRight", path: nextCourse.course_id ? `/courses/${nextCourse.course_id}` : "/courses" },
      secondaryAction: { label: "生成预习建议", icon: "PhSparkle", path: counselorPath(`根据我的课程安排，帮我为${courseName}生成一份简洁预习建议`) },
    }, input, validNow, nextExam);
  }

  const daysToExam = nextExam ? Math.ceil((examTime(nextExam) - validNow.getTime()) / DAY_MS) : Number.POSITIVE_INFINITY;
  if (nextExam && daysToExam <= 7) {
    const courseName = nextExam.course_name || "下一场考试";
    return buildCommand("exam", {
      eyebrow: "基于考试安排",
      headline: `为${courseName}考试留出复习时间`,
      detail: `${formatMonthDay(nextExam.exam_date)}${nextExam.start_time ? ` ${nextExam.start_time}` : ""}${nextExam.location ? ` · ${nextExam.location}` : ""}。现在安排复习，避免临近考试集中赶进度。`,
      primaryAction: { label: "查看考试", icon: "PhArrowRight", path: "/exams" },
      secondaryAction: { label: "制定复习计划", icon: "PhSparkle", path: counselorPath(`结合我的课程和考试安排，为${courseName}制定复习计划`) },
    }, input, validNow, nextExam);
  }

  return buildCommand("focus", {
    eyebrow: "基于当前课程与任务",
    headline: "给今天安排一段完整的学习时间",
    detail: "当前没有紧迫的校园事项。选一个明确目标，完成一次可记录、可复盘的专注学习。",
    primaryAction: { label: "开始专注", icon: "PhPlay", path: "/study" },
    secondaryAction: { label: "整理本周计划", icon: "PhSparkle", path: counselorPath("结合我的课程、任务和考试，帮我整理本周学习计划") },
  }, input, validNow, nextExam);
}