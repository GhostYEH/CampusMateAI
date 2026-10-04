import test, { after } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { Simulate } from "react-dom/test-utils";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { createServer } from "vite";
import { fileURLToPath } from "node:url";

const dom = new JSDOM("<!doctype html><html><body></body></html>", { url: "http://localhost", pretendToBeVisual: true });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.localStorage = dom.window.localStorage;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true, watch: null }, appType: "custom", logLevel: "silent",
  plugins: [{
    name: "profile-notice-race-doubles", enforce: "pre",
    resolveId(source, importer) {
      if (source === "../data/api.js" && /\/pages\/(ProfilePage|ProfileSecondaryPage|IslandPage|NoticeCenterPage)\.jsx$/.test(importer || "")) return "\0profile-notice-api";
      if (importer?.endsWith("/pages/IslandPage.jsx")) {
        if (source.endsWith("LearningIsland.tsx")) return "\0island-view";
        if (source.endsWith("Heatmap.jsx")) return "\0island-heatmap";
        if (source.endsWith("SummerNavDock.jsx")) return "\0profile-notice-stub";
        if (source.endsWith("ambientSound.js")) return "\0island-audio";
      }
      if (source === "../app/AppContext.jsx" && importer?.endsWith("/pages/ProfilePage.jsx")) return "\0profile-notice-context";
      if (["../components/settings/SkeuomorphicGlassToggle.jsx", "../components/FloatingNav/LiquidMetalNav.jsx", "../components/TargetCursor.jsx"].includes(source) && importer?.endsWith("/pages/ProfilePage.jsx")) return "\0profile-notice-stub";
      if (source === "./Icon.jsx" && /\/components\/(Primitives|pages\/ProfilePage)\.jsx$/.test(importer || "")) return "\0profile-notice-icon";
    },
    load(id) {
      if (id === "\0profile-notice-api") return `
        const api = () => globalThis.__profileNoticeApi;
        export const getProfile = (...args) => api().getProfile(...args);
        export const getDashboard = (...args) => api().getDashboard(...args);
        export const getStudySessions = (...args) => api().getStudySessions(...args);
        export const getStudyCheckins = (...args) => api().getStudyCheckins(...args);
        export const updateProfile = (...args) => api().updateProfile(...args);
        export const getNotices = (...args) => api().getNotices(...args);
        export const markAnnouncementRead = (...args) => api().markAnnouncementRead(...args);
        export const extractNotice = (...args) => api().extractNotice(...args);
        export const createTask = (...args) => api().createTask(...args);
      `;
      if (id === "\0profile-notice-context") return `export function useApp(){return {pendingCount:0,reduceMotion:false,setReduceMotion(){},logout(){}}}`;
      if (id === "\0profile-notice-stub") return `export default function Stub(props){return props.children || null}`;
      if (id === "\0profile-notice-icon") return `export function Icon(){return null}`;
      if (id === "\0island-view") return `export function LearningIsland(props){globalThis.__islandView = props; return null}`;
      if (id === "\0island-heatmap") return `export function Heatmap({data}){globalThis.__islandHeatmap = data; return null}`;
      if (id === "\0island-audio") return `export function useAmbientSound(){return {}}`;
    },
  }],
});

test("a failed checkin probe preserves successful study sessions and their heatmap", async () => {
  const today = new Date().toISOString();
  globalThis.__profileNoticeApi = {
    getStudySessions: async () => [{ id: "session", started_at: today, status: "completed", duration_seconds: 3600 }],
    getStudyCheckins: async () => { throw new Error("health probe unavailable"); },
  };
  const { default: IslandPage } = await vite.ssrLoadModule("/src/pages/IslandPage.jsx");
  const view = await mount(IslandPage);
  try {
    assert.equal(globalThis.__islandView.totalHours, 1);
    assert.ok(globalThis.__islandHeatmap.some((day) => day.checked));
    assert.match(view.host.textContent, /签到数据加载失败/);
  } finally { await view.unmount(); delete globalThis.__profileNoticeApi; delete globalThis.__islandView; delete globalThis.__islandHeatmap; }
});

test("a failed session request preserves successful checkins", async () => {
  globalThis.__profileNoticeApi = {
    getStudySessions: async () => { throw new Error("sessions unavailable"); },
    getStudyCheckins: async () => ({ items: [{ date: new Date().toISOString().slice(0, 10) }], total: 3, streak: 2 }),
  };
  const { default: IslandPage } = await vite.ssrLoadModule("/src/pages/IslandPage.jsx");
  const view = await mount(IslandPage);
  try {
    assert.equal(globalThis.__islandView.totalCheckins, 3);
    assert.match(view.host.textContent, /学习记录加载失败/);
  } finally { await view.unmount(); delete globalThis.__profileNoticeApi; delete globalThis.__islandView; delete globalThis.__islandHeatmap; }
});

test("simultaneous island failures display both errors", async () => {
  globalThis.__profileNoticeApi = {
    getStudySessions: async () => { throw new Error("sessions unavailable"); },
    getStudyCheckins: async () => { throw new Error("checkins unavailable"); },
  };
  const { default: IslandPage } = await vite.ssrLoadModule("/src/pages/IslandPage.jsx");
  const view = await mount(IslandPage);
  try {
    assert.match(view.host.querySelector('[role="alert"]').textContent, /学习记录加载失败/);
    assert.match(view.host.querySelector('[role="alert"]').textContent, /签到数据加载失败/);
  } finally { await view.unmount(); delete globalThis.__profileNoticeApi; }
});

test("profile sections only load data needed for their content", async () => {
  let profileRequests = 0;
  globalThis.__profileNoticeApi = {
    getProfile: async () => { profileRequests += 1; throw new Error("profile unavailable"); },
    getStudySessions: async () => [{ id: "s1", goal: "已成功加载的学习记录", status: "completed" }],
  };
  const { ProfileSectionPage } = await vite.ssrLoadModule("/src/pages/ProfileSecondaryPage.jsx");
  function Page() { return createElement(Routes, null, createElement(Route, { path: "/profile/:section", element: createElement(ProfileSectionPage) })); }
  for (const section of ["learning", "favorites", "id-card"]) {
    const view = await mount(Page, `/profile/${section}`);
    try {
      if (section === "learning") assert.match(view.host.textContent, /已成功加载的学习记录/);
      assert.equal(Boolean(view.host.querySelector('[role="alert"]')), section === "id-card");
    } finally { await view.unmount(); }
  }
  assert.equal(profileRequests, 1);
  delete globalThis.__profileNoticeApi;
});
after(async () => { await vite.close(); dom.window.close(); });

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

async function mount(Page, initialEntry = "/") {
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  await act(async () => root.render(createElement(MemoryRouter, { initialEntries: [initialEntry] }, createElement(Page))));
  return { host, async unmount() { await act(async () => root.unmount()); host.remove(); } };
}

test("a late profile save cannot close a newer editing session", async () => {
  const save = deferred();
  globalThis.__profileNoticeApi = {
    getProfile: async () => ({ display_name: "旧姓名", student_number: "S1" }),
    getDashboard: async () => ({}), getStudySessions: async () => [], updateProfile: () => save.promise,
  };
  const { default: ProfilePage } = await vite.ssrLoadModule("/src/pages/ProfilePage.jsx");
  const view = await mount(ProfilePage);
  try {
    await act(async () => new Promise((resolve) => setTimeout(resolve, 30)));
    await act(async () => view.host.querySelector(".text-action").click());
    await act(async () => view.host.querySelector(".profile-edit-form button.primary").click());
    await act(async () => view.host.querySelector(".profile-edit-form button.secondary").click());
    await act(async () => view.host.querySelector(".text-action").click());
    await act(async () => save.resolve({ display_name: "旧请求返回姓名", student_number: "S1" }));
    assert.ok(view.host.querySelector(".profile-edit-form"), "late save must not close the newly opened editor");
  } finally {
    await view.unmount();
    delete globalThis.__profileNoticeApi;
  }
});

test("profile editing saves supported fields and keeps email read-only", async () => {
  let submitted;
  globalThis.__profileNoticeApi = {
    getProfile: async () => ({ display_name: "原姓名", college: "学院", major: "专业", grade: "一年级" }),
    getDashboard: async () => ({}), getStudySessions: async () => [],
    updateProfile: async (payload) => { submitted = payload; return payload; },
  };
  const { default: ProfilePage } = await vite.ssrLoadModule("/src/pages/ProfilePage.jsx");
  const view = await mount(ProfilePage);
  try {
    await act(async () => view.host.querySelector(".text-action").click());
    const email = view.host.querySelector('input[type="email"]');
    assert.equal(email.readOnly, true);
    assert.match(view.host.querySelector("#profile-email-help").textContent, /暂不支持修改邮箱/);
    const name = view.host.querySelector(".profile-edit-form input");
    await act(async () => Simulate.change(name, { target: { value: "新姓名" } }));
    await act(async () => view.host.querySelector(".profile-edit-form button.primary").click());
    assert.deepEqual(submitted, { display_name: "新姓名", college: "学院", major: "专业", grade: "一年级" });
    assert.match(view.host.textContent, /新姓名/);
    assert.match(view.host.textContent, /资料已保存/);
  } finally { await view.unmount(); delete globalThis.__profileNoticeApi; }
});

test("notice save response cannot mark an edited draft saved and saving state settles", async () => {
  const save = deferred();
  let extractCalls = 0;
  globalThis.__profileNoticeApi = {
    getNotices: async () => [], markAnnouncementRead: async () => {},
    extractNotice: async () => { extractCalls += 1; return { tasks: [{ task: extractCalls === 1 ? "原始待办" : "重新提取的待办", source_text: "通知正文" }] }; },
    createTask: () => save.promise,
  };
  const { default: NoticeCenterPage } = await vite.ssrLoadModule("/src/pages/NoticeCenterPage.jsx");
  const view = await mount(NoticeCenterPage, "/?extract=通知正文");
  try {
    await act(async () => new Promise((resolve) => setTimeout(resolve, 30)));
    await act(async () => view.host.querySelector(".extract-submit")?.click());
    assert.equal(extractCalls, 1);
    const saveButton = [...view.host.querySelectorAll("button")].find((button) => button.textContent.includes("保存为待办"));
    await act(async () => saveButton.click());
    const title = view.host.querySelector(".extract-result input");
    await act(async () => Simulate.change(title, { target: { value: "后来修改的待办" } }));
    assert.equal(title.value, "后来修改的待办");
    await act(async () => view.host.querySelector(".extract-submit")?.click());
    assert.equal(extractCalls, 2, "a newer extraction replaces the source version while save is pending");
    await act(async () => save.resolve({ id: "saved-old-draft" }));
    assert.match(view.host.textContent, /保存为待办/);
    assert.doesNotMatch(view.host.textContent, /已保存到待办/);
    assert.equal(view.host.querySelector("button.extract-submit")?.disabled, false);
  } finally {
    await view.unmount();
    delete globalThis.__profileNoticeApi;
  }
});

test("late notice refresh cannot undo a successful mark-read response", async () => {
  const staleRefresh = deferred();
  const markRead = deferred();
  let reads = 0;
  globalThis.__profileNoticeApi = {
    getNotices() {
      reads += 1;
      return reads === 1 ? Promise.resolve([{ kind: "announcement", id: "n1", title: "未读公告", content: "通知内容", has_read: false }]) : staleRefresh.promise;
    },
    markAnnouncementRead: () => markRead.promise,
    extractNotice: async () => ({}), createTask: async () => ({}),
  };
  const { default: NoticeCenterPage } = await vite.ssrLoadModule("/src/pages/NoticeCenterPage.jsx");
  const view = await mount(NoticeCenterPage);
  try {
    await act(async () => new Promise((resolve) => setTimeout(resolve, 30)));
    await act(async () => view.host.querySelector(".list-row").click());
    await act(async () => [...view.host.querySelectorAll("button")].find((button) => button.textContent.includes("刷新通知")).click());
    assert.equal(reads, 2);
    await act(async () => markRead.resolve({}));
    await act(async () => staleRefresh.resolve([{ kind: "announcement", id: "n1", title: "未读公告", content: "通知内容", has_read: false }]));
    assert.doesNotMatch(view.host.querySelector(".notice-row").className, /unread/);
    assert.match(view.host.querySelector(".notice-list-kicker").textContent, /0 条未读通知/);
  } finally {
    await view.unmount();
    delete globalThis.__profileNoticeApi;
  }
});
