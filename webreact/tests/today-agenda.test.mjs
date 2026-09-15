/**
 * 全站统一"今日待办"的前端契约测试。
 *
 * 关键点用**真实渲染**验证（vite ssrLoadModule + renderToStaticMarkup）：
 * 学习陪伴右侧"今日待办"只展示前 8 条，但标题处的总数/完成数必须来自 summary，
 * 而不是对截断后的数组再统计一遍 —— 这正是"77 件待完成"的成因。
 *
 * 另覆盖：三端同源（首页/学习陪伴/任务总览只读 /agenda/today）、学习通条目只读、
 * loading/empty/stale/partial/未绑定/登录态过期 的区分、并发请求去重。
 *
 * 说明：仓库未引入 jsdom，因此这里是 SSR 渲染而非 DOM 交互；effect 不会执行，
 * 所以"刷新后一致"这类行为通过共享数据层的纯函数与渲染结果来验证。
 */
import test, { after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { createServer } from "vite";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import "./helpers/setup-globals.mjs";
import * as apiModule from "../src/data/api.js";
import { createMockClient } from "./helpers/mock-client.mjs";

import * as A from "../src/data/agendaModel.js";

const here = dirname(fileURLToPath(import.meta.url));
const read = (rel) => readFileSync(resolve(here, "..", rel), "utf8");

const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true },
  appType: "custom",
  logLevel: "silent",
});

after(async () => { await vite.close(); });

const { default: SummerFocusRoom } = await vite.ssrLoadModule(
  "/src/components/study/SummerFocusRoom.jsx",
);
const { StaticRouter } = await import("react-router-dom/server.mjs");

const mock = createMockClient(apiModule.client);

// ---------- 后端响应样例（结构与 /agenda/today 契约一致） ----------

function agendaPayload(overrides = {}) {
  return {
    date: "2026-09-15",
    timezone: "Asia/Shanghai",
    generated_at: "2026-09-15T04:00:00+00:00",
    last_chaoxing_synced_at: "2026-09-15T03:00:00+00:00",
    stale: false,
    summary: { total: 2, pending: 1, completed: 1, overdue: 0 },
    sources: {
      chaoxing: { state: "ok", message: null, item_count: 2, last_synced_at: "2026-09-15T03:00:00+00:00" },
      personal: { state: "ok", message: null, item_count: 0, last_synced_at: null },
      schedule: { state: "unavailable", message: "还没有导入课表", item_count: 0, last_synced_at: null },
    },
    items: [
      {
        id: "chaoxing-assignment:ptask_1", source: "chaoxing", kind: "assignment",
        source_id: "ptask_1", course_id: "crs_1", course_name: "高等数学",
        title: "第三章作业", description: null, starts_at: null,
        deadline: "2026-09-15T23:59:59+08:00", status: "pending", priority: "high",
        editable: false, completable: false, route: "/tasks/chaoxing/ptask_1",
        source_url: "https://mooc1.chaoxing.com/work/view?workId=1",
        last_synced_at: "2026-09-15T03:00:00+00:00",
      },
      {
        id: "personal:ptask_2", source: "personal", kind: "personal_task",
        source_id: "ptask_2", course_id: null, course_name: null,
        title: "今天写完实验报告", description: null, starts_at: null,
        deadline: "2026-09-15T18:00:00+08:00", status: "completed", priority: "medium",
        editable: true, completable: true, route: "/tasks/personal/ptask_2",
        source_url: null, last_synced_at: null,
      },
    ],
    ...overrides,
  };
}

function pendingItem(index) {
  return {
    id: `personal:ptask_${index}`, source: "personal", kind: "personal_task",
    source_id: `ptask_${index}`, course_id: null, course_name: null,
    title: `待办 ${index}`, description: null, starts_at: null,
    deadline: null, status: "pending", priority: "medium",
    editable: true, completable: true, route: `/tasks/personal/ptask_${index}`,
    source_url: null, last_synced_at: null,
  };
}

// ---------- 归一化 ----------

test("normalizeTodayAgendaItem maps backend contract to a stable view model", () => {
  const [assignment, personal] = A.normalizeTodayAgenda(agendaPayload()).items;

  assert.equal(assignment.kindLabel, "课程作业");
  assert.equal(assignment.sourceLabel, "学习通");
  assert.equal(assignment.statusLabel, "待完成");
  assert.equal(assignment.readOnly, true);
  assert.equal(assignment.completable, false);
  assert.equal(assignment.route, "/tasks/chaoxing/ptask_1");

  assert.equal(personal.readOnly, false);
  assert.equal(personal.done, true);
  assert.equal(personal.statusLabel, "已完成");
});

test("normalizeTodayAgenda never trusts unparsable payloads", () => {
  assert.equal(A.normalizeTodayAgenda(null), null);
  assert.equal(A.normalizeTodayAgenda(undefined), null);
  const empty = A.normalizeTodayAgenda({});
  assert.deepEqual(empty.items, []);
  assert.deepEqual(empty.summary, { total: 0, pending: 0, completed: 0, overdue: 0 });
});

test("unknown kinds and statuses fall back safely instead of crashing the page", () => {
  const item = A.normalizeTodayAgendaItem({ kind: "telepathy", status: "vibing", title: "" });
  assert.equal(item.kindLabel, "事项");
  assert.equal(item.statusLabel, "待完成");
  assert.equal(item.title, "未命名事项");
  assert.equal(item.done, false);
});

test("source URLs are only exposed for trusted chaoxing https hosts", () => {
  assert.equal(A.isTrustedChaoxingUrl("https://mooc1.chaoxing.com/work/view"), true);
  assert.equal(A.isTrustedChaoxingUrl("https://chaoxing.com/x"), true);
  // fail-closed: 非学习通域名、http、伪装域名一律不放行
  assert.equal(A.isTrustedChaoxingUrl("http://mooc1.chaoxing.com/x"), false);
  assert.equal(A.isTrustedChaoxingUrl("https://chaoxing.com.evil.test/x"), false);
  assert.equal(A.isTrustedChaoxingUrl("https://evil.test/chaoxing.com"), false);
  assert.equal(A.isTrustedChaoxingUrl(""), false);
  assert.equal(A.isTrustedChaoxingUrl(null), false);

  const item = A.normalizeTodayAgendaItem({ source_url: "https://evil.test/x" });
  assert.equal(item.sourceUrl, null);
});

// ---------- 空状态 / 新鲜度必须可区分 ----------

test("empty state distinguishes not-bound, never-synced and genuinely empty", () => {
  const notBound = A.resolveAgendaEmptyState(A.normalizeTodayAgenda(agendaPayload({
    items: [], summary: { total: 0, pending: 0, completed: 0, overdue: 0 },
    sources: { chaoxing: { state: "not_bound" }, personal: {}, schedule: {} },
  })));
  assert.equal(notBound.kind, "not-bound");

  const neverSynced = A.resolveAgendaEmptyState(A.normalizeTodayAgenda(agendaPayload({
    items: [], summary: { total: 0, pending: 0, completed: 0, overdue: 0 },
    sources: { chaoxing: { state: "never_synced" }, personal: {}, schedule: {} },
  })));
  assert.equal(neverSynced.kind, "never-synced");

  const trulyEmpty = A.resolveAgendaEmptyState(A.normalizeTodayAgenda(agendaPayload({
    items: [], summary: { total: 0, pending: 0, completed: 0, overdue: 0 },
  })));
  assert.equal(trulyEmpty.kind, "empty");

  // 有数据时不该出现空状态
  assert.equal(A.resolveAgendaEmptyState(A.normalizeTodayAgenda(agendaPayload())), null);
  // 请求失败要如实报错，不能伪装成"今天没有待办"
  assert.equal(A.resolveAgendaEmptyState(null, { error: "加载失败" }).kind, "error");
});

test("freshness notice covers stale, expired session and partial failures", () => {
  const stale = A.resolveAgendaFreshnessNotice(A.normalizeTodayAgenda(agendaPayload({ stale: true })));
  assert.match(stale, /不是最新/);

  // 登录态来自 /chaoxing/status 的探测结果（今日待办自身不触网），
  // 因此既支持随响应下发的 auth_state，也支持调用方单独传入。
  const expiredFromPayload = A.resolveAgendaFreshnessNotice(A.normalizeTodayAgenda(agendaPayload({
    sources: { chaoxing: { state: "ok", auth_state: "expired" }, personal: {}, schedule: {} },
  })));
  assert.match(expiredFromPayload, /登录态已过期/);

  const expiredFromProbe = A.resolveAgendaFreshnessNotice(
    A.normalizeTodayAgenda(agendaPayload()),
    { authState: "expired" },
  );
  assert.match(expiredFromProbe, /登录态已过期/);

  const partial = A.resolveAgendaFreshnessNotice(A.normalizeTodayAgenda(agendaPayload({
    sources: { chaoxing: { state: "partial" }, personal: {}, schedule: {} },
  })));
  assert.match(partial, /部分课程同步失败/);

  assert.equal(A.resolveAgendaFreshnessNotice(A.normalizeTodayAgenda(agendaPayload())), "");
});

test("unknown auth state is never reported as expired", () => {
  const agenda = A.normalizeTodayAgenda(agendaPayload());
  assert.equal(agenda.sources.chaoxing.authState, "unknown");
  assert.equal(A.resolveAgendaFreshnessNotice(agenda, { authState: "unknown" }), "");
  assert.equal(A.resolveAgendaFreshnessNotice(agenda, { authState: "online" }), "");
});

// ---------- 统一 API ----------

test("getTodayAgenda calls the single shared endpoint", async () => {
  mock.reset();
  mock.onGet("/agenda/today", agendaPayload());
  const payload = await apiModule.getTodayAgenda();
  assert.equal(mock.findRequests("get", "/agenda/today").length, 1);
  assert.equal(payload.summary.pending, 1);
});

test("home, study and tasks pages all read the unified agenda source", () => {
  // 三个页面都必须消费统一今日待办；首页不得再退回 dashboard.due_soon_*。
  const home = read("src/pages/HomePage.jsx");
  assert.match(home, /buildAgendaDueItems/);
  assert.doesNotMatch(home, /buildDueItems\(dashboard\)/);
  assert.match(home, /todayAgenda\.summary\.pending/);

  const study = read("src/pages/StudyPage.jsx");
  assert.match(study, /selectAgendaForSidebar/);
  assert.doesNotMatch(study, /api\.getTasks\(\)/);

  const tasks = read("src/pages/TasksPage.jsx");
  assert.match(tasks, /groupTasksWithAgenda/);

  // 全局角标也来自同一个 summary
  const context = read("src/app/AppContext.jsx");
  assert.match(context, /todayAgenda\.summary\.pending/);
  // 今日待办不触网，登录态过期只能靠一次非阻塞探测来补齐
  assert.match(context, /getChaoxingStatus/);
  assert.match(context, /chaoxingAuthState/);
});

// ---------- 并发去重 ----------

test("concurrent agenda refreshes collapse into a single request", async () => {
  let calls = 0;
  const runOnce = A.createInFlightDeduper();
  const load = () => { calls += 1; return new Promise((r) => setTimeout(() => r("ok"), 5)); };

  const results = await Promise.all([runOnce(load), runOnce(load), runOnce(load), runOnce(load)]);
  assert.equal(calls, 1, "并发调用只应触发一次请求");
  assert.deepEqual(results, ["ok", "ok", "ok", "ok"]);

  // 完成后必须能再次发起（去重不能把后续刷新永久锁死）
  await runOnce(load);
  assert.equal(calls, 2);
});

// ---------- 真实渲染：学习陪伴右侧 ----------

function renderRoom(overrides = {}) {
  const agenda = A.normalizeTodayAgenda(overrides.agenda || agendaPayload());
  const sidebar = A.selectAgendaForSidebar(agenda, 8);
  const html = renderToStaticMarkup(createElement(StaticRouter, { location: "/study" },
    createElement(SummerFocusRoom, {
    active: null,
    pomodoro: { mode: "focus", isRunning: false, focusMinutes: 25, breakMinutes: 5, round: 1 },
    seconds: 1500,
    goal: "",
    preset: 25,
    customMinutes: 45,
    mode: "deep",
    blockNotifications: true,
    whiteNoise: { enabled: false, volume: 0.4, toggle: () => {}, setVolume: () => {} },
    tasks: sidebar.items,
    taskTotal: sidebar.summary.total,
    taskCompleted: sidebar.summary.completed,
    taskPending: sidebar.summary.pending,
    agendaNotice: overrides.notice || "",
    dailyGoalMinutes: 60,
    todayFocusMinutes: 0,
    scene: "summer",
    onSelectScene: () => {},
    ...overrides.props,
  })));
  return { html, sidebar };
}

test("study sidebar caps the list at 8 but reports the real total from summary", () => {
  // 77 条未完成：列表只渲染 8 条，标题处必须显示 77 而不是 8。
  const items = Array.from({ length: 77 }, (_, index) => pendingItem(index));
  const { html } = renderRoom({
    agenda: agendaPayload({
      items,
      summary: { total: 80, pending: 77, completed: 3, overdue: 0 },
    }),
  });

  const rendered = html.match(/待办 \d+/g) || [];
  assert.equal(rendered.length, 8, "列表最多渲染 8 条");
  assert.match(html, /77 件等待完成/, "总数必须来自 summary，而不是截断后的数组");
  assert.match(html, /3\/80 已完成/);
  assert.doesNotMatch(html, /8 件等待完成/);
});

test("study sidebar does not present every historical pending task as today", () => {
  // 只有统一今日待办给出的条目会进入右侧，历史遗留待办不在其中。
  const { html } = renderRoom({
    agenda: agendaPayload({ items: [pendingItem(1)], summary: { total: 1, pending: 1, completed: 0, overdue: 0 } }),
  });
  assert.match(html, /1 件等待完成/);
  assert.equal((html.match(/待办 \d+/g) || []).length, 1);
});

test("chaoxing items render read-only in the study sidebar", () => {
  const { html } = renderRoom();

  // 学习通作业: 没有勾选框的可点击语义，带 data-readonly 标记与锁图标。
  assert.match(html, /data-readonly="true"/);
  assert.match(html, /学习通 · /);
  assert.doesNotMatch(html, /aria-pressed="true"/);
  // 个人待办仍然是可勾选的
  assert.match(html, /aria-pressed="false"/);
});

test("study sidebar surfaces the stale notice instead of pretending data is fresh", () => {
  const { html } = renderRoom({ notice: "学习通数据可能不是最新，建议重新同步后再确认。" });
  assert.match(html, /可能不是最新/);
});

// ---------- 任务总览分组 ----------

const agendaForGrouping = () => A.normalizeTodayAgenda(agendaPayload({
  items: [
    { ...pendingItem(1), kind: "assignment", source: "chaoxing", sourceId: "ptask_1",
      source_id: "ptask_1", completable: false, editable: false },
    { ...pendingItem(2) },
  ],
  summary: { total: 2, pending: 2, completed: 0, overdue: 0 },
}));

test("tasks page today group comes from the agenda and is not duplicated elsewhere", () => {
  const groups = A.groupTasksWithAgenda({
    tasks: [
      { sourceId: "ptask_1", kind: "personal", title: "第三章作业", deadline: "2026-09-15T23:59:59+08:00" },
      { sourceId: "ptask_2", kind: "personal", title: "待办 2", deadline: "2026-09-15T18:00:00+08:00" },
      { sourceId: "ptask_9", kind: "personal", title: "下周的事", deadline: "2026-09-20T18:00:00+08:00" },
    ],
    agenda: agendaForGrouping(),
    stateOf: (task) => {
      if (String(task.deadline).startsWith("2026-09-20")) return "upcoming";
      return "today";
    },
  });

  assert.deepEqual(groups.today.map((item) => item.sourceId), ["ptask_1", "ptask_2"]);
  // 已被"今天"覆盖的条目不能再出现在别的分组
  assert.equal(groups.upcoming.length, 1);
  assert.equal(groups.upcoming[0].sourceId, "ptask_9");
  assert.equal(groups.later.length, 0);
  assert.equal(groups.completed.length, 0);
});

test("tasks page keeps completed and later items when no agenda is available", () => {
  const groups = A.groupTasksWithAgenda({
    tasks: [
      { sourceId: "a", done: true },
      { sourceId: "b", done: false },
    ],
    agenda: null,
    stateOf: (task) => (task.done ? "completed" : "later"),
  });
  assert.deepEqual(groups.today, []);
  assert.deepEqual(groups.completed.map((t) => t.sourceId), ["a"]);
  assert.deepEqual(groups.later.map((t) => t.sourceId), ["b"]);
});

// ---------- 首页映射 ----------

test("home due items keep the backend order and only include pending work", () => {
  const due = A.buildAgendaDueItems(A.normalizeTodayAgenda(agendaPayload()));
  assert.equal(due.length, 1);
  assert.equal(due[0].title, "第三章作业");
  assert.equal(due[0].route, "/tasks/chaoxing/ptask_1");
  assert.equal(due[0].due, "2026-09-15T23:59:59+08:00");
});
