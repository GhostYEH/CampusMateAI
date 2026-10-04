import test, { after, afterEach } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { createServer } from "vite";
import { fileURLToPath } from "node:url";

const dom = new JSDOM("<!doctype html><html><body></body></html>", { url: "http://localhost" });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true, watch: null }, appType: "custom", logLevel: "silent",
  plugins: [{
    name: "quiz-api-test-double", enforce: "pre",
    resolveId(source, importer) {
      if (source === "../../data/api.js" && importer?.endsWith("/QuizRuntimePanel.jsx")) return "\0quiz-api-test-double";
    },
    load(id) {
      if (id !== "\0quiz-api-test-double") return null;
      return `
        export const getMagicClassQuizAttempt = (...args) => globalThis.__quizApi.get(...args);
        export const saveMagicClassQuizAttempt = (...args) => globalThis.__quizApi.save(...args);
      `;
    },
  }],
});
const { default: QuizRuntimePanel } = await vite.ssrLoadModule("/src/components/magicclass/QuizRuntimePanel.jsx");
after(async () => { await vite.close(); dom.window.close(); });
afterEach(() => { window.localStorage.clear(); delete globalThis.__quizApi; });

const questions = [{ id: "q1", question: "选择正确答案", options: ["A", "B"], answer: "A", analysis: "答案是 A", points: 2 }];
const props = { questions, courseId: "course", workspaceId: "workspace", stageId: "stage", sceneId: "scene" };
function deferred() {
  let resolve;
  const promise = new Promise((yes) => { resolve = yes; });
  return { promise, resolve };
}
async function mount(extra = {}) {
  const host = document.createElement("div"); document.body.append(host);
  const root = createRoot(host);
  await act(async () => root.render(createElement(QuizRuntimePanel, { ...props, ...extra })));
  return { host, root, close: async () => { await act(async () => root.unmount()); host.remove(); } };
}
async function click(host, label) {
  const button = [...host.querySelectorAll("button")].find((item) => item.textContent === label);
  assert.ok(button, `button ${label} exists`);
  await act(async () => button.click());
}
async function choose(host, index = 0) {
  await act(async () => host.querySelectorAll('input[type="radio"]')[index].click());
}

test("failed draft remains visible and retry sends the latest answers", async () => {
  let fail = false;
  const calls = [];
  globalThis.__quizApi = {
    get: async () => ({ attempt_id: "attempt", state: null }),
    save: async (...args) => {
      calls.push(args.at(-1));
      if (fail) throw { response: { data: { message: "保存服务暂不可用", detail: "internal" }, status: 503 } };
      return { attempt_id: "attempt" };
    },
  };
  const view = await mount();
  try {
    await click(view.host, "开始答题");
    fail = true;
    await choose(view.host);
    assert.match(view.host.querySelector('[role="alert"]').textContent, /保存服务暂不可用/);
    assert.equal(view.host.querySelector('input[value="A"]').checked, true);
    assert.equal(JSON.parse(window.localStorage.getItem("campusmate:magicclass:quiz:scene")).pending_sync, true);
    fail = false;
    await click(view.host, "重试同步");
    assert.equal(view.host.querySelector('[role="alert"]'), null);
    assert.deepEqual(calls.at(-1).answers, { q1: "A" });
    assert.equal(JSON.parse(window.localStorage.getItem("campusmate:magicclass:quiz:scene")).pending_sync, false);
  } finally { await view.close(); }
});

test("submission waits for drafts and cannot be overwritten by a late draft", async () => {
  const delayed = deferred(); const calls = [];
  globalThis.__quizApi = {
    get: async () => ({ attempt_id: "attempt", state: null }),
    save: async (...args) => {
      calls.push(args.at(-1));
      if (calls.length === 2) await delayed.promise;
      return { attempt_id: "attempt" };
    },
  };
  const view = await mount();
  try {
    await click(view.host, "开始答题");
    await choose(view.host);
    await click(view.host, "提交答案");
    assert.deepEqual(calls.map((call) => call.phase), ["draft", "draft"]);
    assert.match(view.host.querySelector('[role="status"]').textContent, /正在同步/);
    await act(async () => delayed.resolve());
    assert.deepEqual(calls.map((call) => call.phase), ["draft", "draft", "submitted", "reviewed"]);
    assert.deepEqual(calls.at(-1).answers, { q1: "A" });
    assert.equal(calls.at(-1).results.length, 1);
    assert.equal(view.host.querySelector('[role="status"]'), null);
  } finally { await view.close(); }
});

test("retry after a lost reviewed response does not move the server backwards", async () => {
  let state = null; let loseResponse = true; const calls = [];
  globalThis.__quizApi = {
    get: async () => ({ attempt_id: "attempt", state }),
    save: async (...args) => {
      const payload = args.at(-1); calls.push(payload); state = payload;
      if (payload.phase === "reviewed" && loseResponse) { loseResponse = false; throw { request: {}, code: "ECONNABORTED" }; }
      return { attempt_id: "attempt" };
    },
  };
  const view = await mount();
  try {
    await click(view.host, "开始答题"); await choose(view.host); await click(view.host, "提交答案");
    assert.match(view.host.querySelector('[role="alert"]').textContent, /同步失败/);
    const beforeRetry = calls.length;
    await click(view.host, "重试同步");
    assert.deepEqual(calls.slice(beforeRetry).map((call) => call.phase), ["reviewed"]);
    assert.equal(view.host.querySelector('[role="alert"]'), null);
  } finally { await view.close(); }
});

test("switching scenes ignores late hydration from the old scene", async () => {
  const old = deferred();
  globalThis.__quizApi = {
    get: async (_course, _workspace, _stage, scene) => scene === "scene" ? old.promise : { attempt_id: "new", state: null },
    save: async () => ({ attempt_id: "attempt" }),
  };
  const view = await mount();
  try {
    await click(view.host, "开始答题");
    assert.equal(view.host.querySelector('input[type="radio"]'), null);
    await act(async () => view.root.render(createElement(QuizRuntimePanel, { ...props, sceneId: "new-scene" })));
    assert.equal(view.host.querySelector('input[type="radio"]'), null);
    await act(async () => old.resolve({ attempt_id: "old", state: { phase: "draft", answers: { q1: "B" } } }));
    await click(view.host, "开始答题");
    assert.equal(view.host.querySelector('input[value="A"]').checked, false);
    assert.equal(view.host.querySelector('input[value="B"]').checked, false);
  } finally { await view.close(); }
});

test("a submitted server attempt without local cache resumes review and can finish synchronization", async () => {
  let state = { phase: "submitted", answers: { q1: "A" }, results: [] };
  const calls = [];
  globalThis.__quizApi = {
    get: async () => ({ attempt_id: "attempt", state }),
    save: async (...args) => {
      const payload = args.at(-1); calls.push(payload);
      if (payload.phase === "draft") throw { response: { status: 409, data: { detail: "测验状态不能回退" } } };
      state = payload;
      return { attempt_id: "attempt" };
    },
  };
  const view = await mount();
  try {
    assert.match(view.host.textContent, /测验完成/);
    assert.match(view.host.querySelector('[role="alert"]').textContent, /答案已提交/);
    assert.match(view.host.querySelector('[data-testid="quiz-score"]').textContent, /2 \/ 2/);
    await click(view.host, "重试同步");
    assert.deepEqual(calls.map((call) => call.phase), ["submitted", "reviewed"]);
    assert.equal(state.phase, "reviewed");
    assert.equal(view.host.querySelector('[role="alert"]'), null);
  } finally { await view.close(); }
});

test("a fast first click waits for the current server retry identity", async () => {
  const initial = deferred(); const calls = [];
  globalThis.__quizApi = {
    get: () => initial.promise,
    save: async (...args) => {
      const payload = args.at(-1); calls.push(payload);
      if (payload.attempt_id !== "root:retry:1") throw { response: { status: 409, data: { detail: "测验状态不能回退" } } };
      return { attempt_id: "root:retry:1" };
    },
  };
  const view = await mount();
  try {
    await click(view.host, "开始答题");
    assert.equal(view.host.querySelector('input[type="radio"]'), null, "start is disabled until hydration finishes");
    assert.equal(calls.length, 0, "writes wait for the server-owned attempt identity");
    await act(async () => initial.resolve({ attempt_id: "root:retry:1", state: { phase: "draft", answers: { q1: "B" }, results: [] } }));
    await choose(view.host);
    assert.deepEqual(calls.map((call) => call.attempt_id), ["root:retry:1"]);
    assert.deepEqual(calls.at(-1).answers, { q1: "A" });
    assert.equal(view.host.querySelector('input[value="A"]').checked, true);
    assert.equal(view.host.querySelector('[role="alert"]'), null);
  } finally { await view.close(); }
});

test("starting before hydration cannot move an already reviewed server attempt backwards", async () => {
  const initial = deferred(); const calls = [];
  globalThis.__quizApi = {
    get: () => initial.promise,
    save: async (...args) => { calls.push(args.at(-1)); return { attempt_id: "root" }; },
  };
  const view = await mount();
  try {
    await click(view.host, "开始答题");
    await act(async () => initial.resolve({ attempt_id: "root", state: { phase: "reviewed", answers: { q1: "A" }, results: [{ correct: true, analysis: "正确" }] } }));
    assert.match(view.host.textContent, /测验完成/);
    assert.equal(calls.length, 0);
  } finally { await view.close(); }
});

test("retrying an uncertain new-attempt write adopts the server attempt instead of creating another", async () => {
  let attempt = "root";
  let state = { phase: "reviewed", answers: { q1: "A" }, results: [{ correct: true, analysis: "正确" }] };
  let creations = 0;
  globalThis.__quizApi = {
    get: async () => ({ attempt_id: attempt, state }),
    save: async (...args) => {
      const payload = args.at(-1);
      if (payload.start_new_attempt) {
        attempt = `root:retry:${++creations}`; state = payload;
        throw { request: {}, code: "ECONNABORTED" };
      }
      assert.equal(payload.attempt_id, attempt);
      state = payload;
      return { attempt_id: attempt };
    },
  };
  const view = await mount();
  try {
    await click(view.host, "重新作答");
    assert.equal(creations, 1);
    assert.match(view.host.querySelector('[role="alert"]').textContent, /同步失败/);
    await click(view.host, "重试同步");
    assert.equal(creations, 1);
    assert.equal(view.host.querySelector('[role="alert"]'), null);
    assert.equal(JSON.parse(window.localStorage.getItem("campusmate:magicclass:quiz:scene")).attempt_id, "root:retry:1");
  } finally { await view.close(); }
});

test("a failed initial read keeps start disabled until the server state is recovered", async () => {
  let reads = 0; const calls = [];
  globalThis.__quizApi = {
    get: async () => {
      if (++reads === 1) throw { request: {}, code: "ERR_NETWORK" };
      return { attempt_id: "root", state: { phase: "reviewed", answers: { q1: "A" }, results: [{ correct: true, analysis: "正确" }] } };
    },
    save: async (...args) => { calls.push(args.at(-1)); return { attempt_id: "root" }; },
  };
  const view = await mount();
  try {
    assert.match(view.host.querySelector('[role="alert"]').textContent, /读取失败/);
    await click(view.host, "开始答题");
    assert.equal(view.host.querySelector('input[type="radio"]'), null);
    await click(view.host, "重试读取");
    assert.match(view.host.textContent, /测验完成/);
    assert.equal(calls.length, 0);
    assert.equal(view.host.querySelector('[role="alert"]'), null);
  } finally { await view.close(); }
});
