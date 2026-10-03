import test, { after } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { Simulate } from "react-dom/test-utils";
import { MemoryRouter } from "react-router-dom";
import { createServer } from "vite";
import { fileURLToPath } from "node:url";

const dom = new JSDOM("<!doctype html><html><body></body></html>", { url: "http://localhost", pretendToBeVisual: true });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame.bind(dom.window);
globalThis.cancelAnimationFrame = dom.window.cancelAnimationFrame.bind(dom.window);

const apiExports = [
  "getAssignments", "getTasks", "completeTask", "createTask", "updateTask", "deleteTask",
  "commitTaskImport", "analyzeTaskImport", "getActiveStudySession", "getStudySessions",
  "getDailyStudyGoal", "startStudySession", "pauseStudySession", "resumeStudySession",
  "finishStudySession", "updateDailyStudyGoal", "breakdownStudyTask",
];
const apiModule = `
  const api = () => globalThis.__pageRaceApi;
  ${apiExports.map((name) => `export const ${name} = (...args) => api().${name}(...args);`).join("\n")}
`;

const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true, watch: null },
  appType: "custom",
  logLevel: "silent",
  plugins: [{
    name: "page-race-test-doubles",
    enforce: "pre",
    resolveId(source, importer) {
      if (source === "../data/api.js" && /\/pages\/(TasksPage|StudyPage)\.jsx$/.test(importer || "")) return "\0page-race-api";
      if (source === "../app/AppContext.jsx" && /\/pages\/(TasksPage|StudyPage)\.jsx$/.test(importer || "")) return "\0page-race-app-context";
      if (source === "../components/study/SummerFocusRoom.jsx" && importer?.endsWith("/pages/StudyPage.jsx")) return "\0page-race-study-room";
      if (source === "../components/study/SummerNavDock.jsx" && importer?.endsWith("/pages/StudyPage.jsx")) return "\0page-race-study-dock";
    },
    load(id) {
      if (id === "\0page-race-api") return apiModule;
      if (id === "\0page-race-app-context") return `export function useApp(){ return { tasks: [], toggleTask(){}, updateTask(){}, deleteTask(){}, todayAgenda: null, agendaError: "", refreshAgenda: () => globalThis.__pageRaceAgenda ? globalThis.__pageRaceAgenda() : Promise.resolve(null) }; }`;
      if (id === "\0page-race-study-room") return `
        import React from "react";
        export default function Room(props) {
          globalThis.__studyRoomProps = props;
          return React.createElement("section", null,
            React.createElement("output", { "data-testid": "active-session" }, props.active?.id || "no-session"),
            React.createElement("output", { "data-testid": "task-total" }, String(props.taskTotal)),
            React.createElement("output", { "data-testid": "task-titles" }, (props.tasks || []).map((task) => task.title).join(",")),
            React.createElement("button", { onClick: () => props.onStart("focus goal") }, "开始专注"),
            React.createElement("button", { onClick: () => props.onAddTask("新增待办") }, "添加待办"),
            React.createElement("button", { onClick: props.onRefresh }, "刷新专注数据"));
        }
      `;
      if (id === "\0page-race-study-dock") return `export default function Dock(){ return null; }`;
    },
  }],
});
after(async () => { await vite.close(); dom.window.close(); });

function deferred() {
  let resolve;
  const promise = new Promise((yes) => { resolve = yes; });
  return { promise, resolve };
}

async function mount(Page) {
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  await act(async () => root.render(createElement(MemoryRouter, null, createElement(Page))));
  return {
    host,
    async unmount() { await act(async () => root.unmount()); host.remove(); },
  };
}

test("two task actions that finish out of order both appear in the final list", async () => {
  const initial = deferred();
  const actionWaits = { first: deferred(), second: deferred() };
  const refreshes = [];
  let taskReads = 0;
  let serverTasks = [
    { id: "first", title: "任务甲", status: "pending", deadline: "2999-01-01T00:00:00Z" },
    { id: "second", title: "任务乙", status: "pending", deadline: "2999-01-02T00:00:00Z" },
  ];
  globalThis.__pageRaceApi = {
    getAssignments: async () => [],
    getTasks() {
      taskReads += 1;
      if (taskReads === 1) return initial.promise;
      const request = deferred();
      refreshes.push({ request, snapshot: serverTasks.map((task) => ({ ...task })) });
      return request.promise;
    },
    completeTask(id) {
      return actionWaits[id].promise.then(() => {
        serverTasks = serverTasks.map((task) => task.id === id ? { ...task, status: "completed" } : task);
      });
    },
  };
  const { default: TasksPage } = await vite.ssrLoadModule("/src/pages/TasksPage.jsx");
  const view = await mount(TasksPage);
  try {
    await act(async () => initial.resolve(serverTasks));
    const rows = [...view.host.querySelectorAll(".task-row")];
    const firstButton = rows.find((row) => row.textContent.includes("任务甲")).querySelector(".task-row-actions button");
    const secondButton = rows.find((row) => row.textContent.includes("任务乙")).querySelector(".task-row-actions button");
    await act(async () => { firstButton.click(); secondButton.click(); });

    await act(async () => actionWaits.second.resolve());
    assert.equal(refreshes.length, 1);
    await act(async () => actionWaits.first.resolve());
    assert.equal(refreshes.length, 2);

    await act(async () => refreshes[1].request.resolve(refreshes[1].snapshot));
    await act(async () => refreshes[0].request.resolve(refreshes[0].snapshot));
    const completed = [...view.host.querySelectorAll(".stat-card")]
      .find((card) => card.textContent.includes("已完成"));
    assert.match(completed.textContent, /2/);
    const completedGroup = [...view.host.querySelectorAll(".task-group-toggle")]
      .find((button) => button.textContent.includes("已完成"));
    await act(async () => completedGroup.click());
    assert.match(view.host.textContent, /任务甲/);
    assert.match(view.host.textContent, /任务乙/);
  } finally {
    await view.unmount();
    delete globalThis.__pageRaceApi;
  }
});

test("a late save cannot close a newer task editor draft", async () => {
  const oldSave = deferred();
  globalThis.__pageRaceApi = {
    getAssignments: async () => [], getTasks: async () => [],
    createTask: () => oldSave.promise,
  };
  const { default: TasksPage } = await vite.ssrLoadModule("/src/pages/TasksPage.jsx");
  const view = await mount(TasksPage);
  try {
    await act(async () => new Promise((resolve) => setTimeout(resolve, 0)));
    const buttons = () => [...document.body.querySelectorAll("button")];
    await act(async () => buttons().find((button) => button.textContent.includes("新建待办")).click());
    const title = document.body.querySelector("#task-editor-title");
    await act(async () => Simulate.change(title, { target: { value: "旧草稿" } }));
    await act(async () => buttons().find((button) => button.textContent.includes("保存待办")).click());
    await act(async () => buttons().find((button) => button.textContent.includes("取消")).click());
    await act(async () => buttons().find((button) => button.textContent.includes("新建待办")).click());
    const newTitle = document.body.querySelector("#task-editor-title");
    await act(async () => Simulate.change(newTitle, { target: { value: "新草稿" } }));
    await act(async () => oldSave.resolve({ id: "old-save" }));
    assert.ok(document.body.querySelector("#task-editor-title"), "the newer editor stays open after old save settles");
    assert.equal(document.body.querySelector("#task-editor-title").value, "新草稿");
  } finally {
    await view.unmount();
    delete globalThis.__pageRaceApi;
  }
});

test("a study start invalidates a late session read and releases its loading state", async () => {
  const staleRead = deferred();
  const startRead = deferred();
  let activeReads = 0;
  globalThis.__pageRaceApi = {
    getActiveStudySession() { activeReads += 1; return activeReads === 1 ? Promise.resolve(null) : staleRead.promise; },
    getStudySessions: async () => [],
    getDailyStudyGoal: async () => ({ target_minutes: 60 }),
    startStudySession: () => startRead.promise,
    finishStudySession: async () => ({}),
  };
  const { default: StudyPage } = await vite.ssrLoadModule("/src/pages/StudyPage.jsx");
  const view = await mount(StudyPage);
  try {
    assert.ok(view.host.querySelector("[data-testid='active-session']"));
    let starting;
    await act(async () => {
      void globalThis.__studyRoomProps.onRefresh();
      starting = globalThis.__studyRoomProps.onStart("focus goal");
    });
    assert.ok(view.host.querySelector("[data-testid='active-session']"), "a newer start owns the visible study panel");

    await act(async () => staleRead.resolve({ id: "stale-session", status: "active", started_at: new Date().toISOString(), planned_duration_seconds: 1500 }));
    assert.equal(view.host.querySelector("[data-testid='active-session']").textContent, "no-session");

    await act(async () => startRead.resolve({ id: "started-session", status: "active" }));
    await act(async () => starting);
    assert.equal(view.host.querySelector("[data-testid='active-session']").textContent, "started-session");
    assert.doesNotMatch(view.host.textContent, /正在加载内容/);
  } finally {
    await view.unmount();
    delete globalThis.__pageRaceApi;
    delete globalThis.__studyRoomProps;
  }
});

test("a successful study start after unmount keeps the server session and does not finish it", async () => {
  const startRead = deferred();
  const finished = [];
  globalThis.__pageRaceApi = {
    getActiveStudySession: async () => null,
    getStudySessions: async () => [],
    getDailyStudyGoal: async () => ({ target_minutes: 60 }),
    startStudySession: () => startRead.promise,
    finishStudySession: async (id) => { finished.push(id); },
  };
  const { default: StudyPage } = await vite.ssrLoadModule("/src/pages/StudyPage.jsx");
  const view = await mount(StudyPage);
  let starting;
  await act(async () => { starting = globalThis.__studyRoomProps.onStart("focus goal"); });
  await view.unmount();
  await act(async () => startRead.resolve({ id: "server-session", status: "active" }));
  await act(async () => starting);
  assert.deepEqual(finished, [], "navigating away must not end the server-side session");
  delete globalThis.__pageRaceApi;
  delete globalThis.__studyRoomProps;
});

test("a session mutation does not discard an unrelated in-flight agenda refresh", async () => {
  const agendaRefresh = deferred();
  const startRead = deferred();
  let agendaReads = 0;
  globalThis.__pageRaceAgenda = () => {
    agendaReads += 1;
    return agendaReads === 1 ? Promise.resolve(null) : agendaRefresh.promise;
  };
  globalThis.__pageRaceApi = {
    getActiveStudySession: async () => null,
    getStudySessions: async () => [],
    getDailyStudyGoal: async () => ({ target_minutes: 60 }),
    createTask: async () => ({ id: "created-task" }),
    startStudySession: () => startRead.promise,
  };
  const { default: StudyPage } = await vite.ssrLoadModule("/src/pages/StudyPage.jsx");
  const view = await mount(StudyPage);
  try {
    await act(async () => new Promise((resolve) => setTimeout(resolve, 0)));
    assert.equal(agendaReads, 1, "the initial study load has completed its agenda refresh");
    assert.equal(view.host.querySelector("[data-testid='task-total']").textContent, "0");
    let starting;
    await act(async () => {
      void globalThis.__studyRoomProps.onAddTask("新增待办");
      starting = globalThis.__studyRoomProps.onStart("focus goal");
    });
    await act(async () => agendaRefresh.resolve({
      summary: { total: 1, pending: 1, completed: 0 },
      items: [{ id: "agenda-1", source_id: "task-1", title: "今日阅读", status: "pending", completable: true }],
    }));
    assert.equal(view.host.querySelector("[data-testid='task-total']").textContent, "1", "the agenda refresh remains valid across an unrelated session start");
    assert.match(view.host.querySelector("[data-testid='task-titles']").textContent, /今日阅读/);

    await act(async () => startRead.resolve({ id: "started-session", status: "active" }));
    await act(async () => starting);
    assert.equal(view.host.querySelector("[data-testid='active-session']").textContent, "started-session");
  } finally {
    await view.unmount();
    delete globalThis.__pageRaceAgenda;
    delete globalThis.__pageRaceApi;
    delete globalThis.__studyRoomProps;
  }
});
