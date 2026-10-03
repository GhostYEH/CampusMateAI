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
globalThis.localStorage = dom.window.localStorage;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true, watch: null }, appType: "custom", logLevel: "silent",
  plugins: [{
    name: "profile-notice-race-doubles", enforce: "pre",
    resolveId(source, importer) {
      if (source === "../data/api.js" && /\/pages\/(ProfilePage|NoticeCenterPage)\.jsx$/.test(importer || "")) return "\0profile-notice-api";
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
        export const updateProfile = (...args) => api().updateProfile(...args);
        export const getNotices = (...args) => api().getNotices(...args);
        export const markAnnouncementRead = (...args) => api().markAnnouncementRead(...args);
        export const extractNotice = (...args) => api().extractNotice(...args);
        export const createTask = (...args) => api().createTask(...args);
      `;
      if (id === "\0profile-notice-context") return `export function useApp(){return {pendingCount:0,reduceMotion:false,setReduceMotion(){},logout(){}}}`;
      if (id === "\0profile-notice-stub") return `export default function Stub(props){return props.children || null}`;
      if (id === "\0profile-notice-icon") return `export function Icon(){return null}`;
    },
  }],
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
