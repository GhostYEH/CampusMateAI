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
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true, watch: null }, appType: "custom", logLevel: "silent",
  plugins: [{ name: "homework-api-double", enforce: "pre",
    resolveId(source, importer) {
      if (source === "../data/api.js" && importer?.endsWith("/components/ChaoxingAssignmentPanel.jsx")) return "\0homework-api-double";
    },
    load(id) {
      if (id !== "\0homework-api-double") return null;
      return ["getChaoxingAssignmentContent", "syncChaoxing", "generateChaoxingAssignmentClassroom", "getMagicClassJob", "retryMagicClassJob"].map((name) => `export const ${name} = (...args) => globalThis.__homeworkApi.${name}(...args);`).join("\n");
    },
  }],
});
after(async () => { await vite.close(); dom.window.close(); });
const { default: Panel } = await vite.ssrLoadModule("/src/components/ChaoxingAssignmentPanel.jsx");
const questions = [{ number: 1, stem: "求x+1", options: ["A.2", "B.3", "C.4"] }];
const button = (host, text) => [...host.querySelectorAll("button")].find((node) => node.textContent.includes(text));

function Location() { const location = useLocation(); return createElement("output", null, location.pathname + location.search); }
async function mount(status) {
  const host = document.createElement("div"); document.body.append(host);
  const root = createRoot(host);
  await act(async () => root.render(createElement(StrictMode, null, createElement(MemoryRouter, null,
    createElement(Panel, { task: { id: "work", status }, onSynced: async () => {} }), createElement(Location)))));
  return { host, async close() { await act(async () => root.unmount()); host.remove(); } };
}

test("unsubmitted work shows real options and keeps review generation disabled", async () => {
  globalThis.__homeworkApi = { getChaoxingAssignmentContent: async () => ({ available: true, current: true, can_generate: false, questions }) };
  const view = await mount("pending");
  try {
    assert.match(view.host.textContent, /B.3/);
    assert.equal(button(view.host, "生成作业讲解").disabled, true);
  } finally { await view.close(); }
});

test("submitted work resumes a failed job and opens its lesson in playback", async () => {
  const calls = [];
  globalThis.__homeworkApi = {
    getChaoxingAssignmentContent: async () => ({ available: true, current: true, can_generate: true, questions }),
    generateChaoxingAssignmentClassroom: async (id) => { calls.push(id); return { course_id: "course", workspace_id: "review", job: { id: "job", status: "failed" } }; },
    retryMagicClassJob: async (course, job) => { calls.push([course, job]); return { id: job, status: "completed", progress: 100 }; },
  };
  const view = await mount("completed");
  try {
    await act(async () => button(view.host, "生成作业讲解").click());
    assert.deepEqual(calls, ["work", ["course", "job"]]);
    await act(async () => button(view.host, "进入课堂学习").click());
    assert.equal(view.host.querySelector("output").textContent, "/courses/course/workspaces/review?mode=playback");
  } finally { await view.close(); }
});

test("missing submitted question snapshot gives a useful error and permits synchronization", async () => {
  let synced = 0;
  globalThis.__homeworkApi = {
    getChaoxingAssignmentContent: async () => ({ available: true, current: true, can_generate: true, questions }),
    generateChaoxingAssignmentClassroom: async () => { throw { response: { data: { message: "assignment_content_not_current" } } }; },
    syncChaoxing: async () => { synced += 1; },
  };
  const view = await mount("completed");
  try {
    await act(async () => button(view.host, "生成作业讲解").click());
    assert.match(view.host.querySelector('[role="alert"]').textContent, /先同步作业/);
    await act(async () => button(view.host, "同步作业与提交状态").click());
    assert.equal(synced, 1);
  } finally { await view.close(); }
});
