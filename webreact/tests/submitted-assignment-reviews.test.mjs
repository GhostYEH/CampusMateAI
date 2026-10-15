import test, { after } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { act, createElement, StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter, useLocation } from "react-router-dom";
import { createServer } from "vite";
import { fileURLToPath } from "node:url";

const dom = new JSDOM("<!doctype html><html><body></body></html>", { url: "http://localhost" });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)), server: { middlewareMode: true, watch: null }, appType: "custom", logLevel: "silent",
  plugins: [{ name: "submitted-review-api", enforce: "pre", resolveId(source, importer) {
    if (source === "../data/api.js" && importer?.endsWith("/components/SubmittedAssignmentReviews.jsx")) return "\0submitted-review-api";
  }, load(id) {
    if (id !== "\0submitted-review-api") return null;
    return ["getTasks", "generateChaoxingAssignmentClassroom", "getMagicClassJob", "retryMagicClassJob", "syncChaoxing"].map((name) => `export const ${name} = (...args) => globalThis.__submittedApi.${name}(...args);`).join("\n");
  } }],
});
after(async () => { await vite.close(); dom.window.close(); });
const { default: Reviews } = await vite.ssrLoadModule("/src/components/SubmittedAssignmentReviews.jsx");
const task = { id: "work", title: "函数作业", source: "chaoxing", source_name: "高等数学", status: "completed", course_id: "course" };
const button = (host, text) => [...host.querySelectorAll("button")].find((node) => node.textContent.includes(text));
const completed = { course_id: "course", workspace_id: "review", job: { id: "job", status: "completed" } };
function Location() { const location = useLocation(); return createElement("output", null, location.pathname + location.search); }
async function mount(compact = false) {
  const host = document.createElement("div"); document.body.append(host); const root = createRoot(host);
  await act(async () => root.render(createElement(StrictMode, null, createElement(MemoryRouter, null, createElement(Reviews, { compact }), createElement(Location)))));
  return { host, async close() { await act(async () => root.unmount()); host.remove(); } };
}

test("classroom list enters an existing review in one click and blocks rapid duplicate clicks", async () => {
  let resolve, calls = 0;
  globalThis.__submittedApi = {
    getTasks: async () => ({ items: [task] }),
    generateChaoxingAssignmentClassroom: () => { calls += 1; return new Promise((done) => { resolve = done; }); },
  };
  const view = await mount();
  try {
    assert.match(view.host.textContent, /高等数学/);
    assert.match(view.host.querySelector("a").href, /\/tasks\/chaoxing\/work$/);
    await act(async () => { button(view.host, "一键进入讲解").click(); button(view.host, "一键进入讲解").click(); });
    assert.equal(calls, 1);
    await act(async () => resolve(completed));
    assert.equal(view.host.querySelector("output").textContent, "/courses/course/workspaces/review?mode=playback");
  } finally { await view.close(); }
});

test("sidebar shows generation progress and automatically opens the finished lesson", async () => {
  globalThis.__submittedApi = {
    getTasks: async () => ({ items: [task] }),
    generateChaoxingAssignmentClassroom: async () => ({ ...completed, job: { id: "job", status: "queued", progress: 20 } }),
    getMagicClassJob: async () => completed.job,
  };
  const view = await mount(true);
  try {
    await act(async () => button(view.host, "一键进入讲解").click());
    assert.match(view.host.textContent, /正在生成讲解 20%/);
    assert.equal(view.host.querySelector("output").textContent, "/");
    await act(async () => new Promise((resolve) => setTimeout(resolve, 2100)));
    assert.equal(view.host.querySelector("output").textContent, "/courses/course/workspaces/review?mode=playback");
  } finally { await view.close(); }
});

test("list failure stays visible and can be refreshed into an empty state", async () => {
  let fail = true;
  globalThis.__submittedApi = { getTasks: async () => { if (fail) throw new Error("offline"); return { items: [] }; } };
  const view = await mount();
  try {
    assert.match(view.host.querySelector('[role="alert"]').textContent, /读取失败/);
    fail = false;
    await act(async () => view.host.querySelector('[aria-label="刷新已提交作业"]').click());
    assert.match(view.host.textContent, /暂无已提交的学习通作业/);
  } finally { await view.close(); }
});
