import test, { after } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { act, createElement, StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Simulate } from "react-dom/test-utils";
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { createServer } from "vite";
import { fileURLToPath } from "node:url";

const dom = new JSDOM("<!doctype html><html><body></body></html>", { url: "http://localhost", pretendToBeVisual: true });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame.bind(dom.window);
globalThis.cancelAnimationFrame = dom.window.cancelAnimationFrame.bind(dom.window);

const pendingPollTimers = new Set();
const nativeSetTimeout = globalThis.setTimeout;
const nativeClearTimeout = globalThis.clearTimeout;
globalThis.setTimeout = (callback, delay, ...args) => {
  let handle;
  const wrapped = (...callbackArgs) => {
    pendingPollTimers.delete(handle);
    callback(...callbackArgs);
  };
  handle = nativeSetTimeout(wrapped, delay, ...args);
  if (delay === 800) pendingPollTimers.add(handle);
  return handle;
};
globalThis.clearTimeout = (handle) => {
  pendingPollTimers.delete(handle);
  return nativeClearTimeout(handle);
};

const apiModule = `
  const api = () => globalThis.__magicHomeLifecycleApi;
  export const generateMagicClassHome = (...args) => api().generateMagicClassHome(...args);
  export const getMagicClassJob = (...args) => api().getMagicClassJob(...args);
`;
const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true, watch: null },
  appType: "custom",
  logLevel: "silent",
  plugins: [{
    name: "magicclass-home-lifecycle-test-doubles",
    enforce: "pre",
    resolveId(source, importer) {
      if (source === "../../data/api.js" && importer?.endsWith("/components/magicclass/magicclassHome.jsx")) return "\0magic-home-lifecycle-api";
      if (source === "../Icon.jsx" && importer?.endsWith("/components/magicclass/magicclassHome.jsx")) return "\0magic-home-lifecycle-icon";
    },
    load(id) {
      if (id === "\0magic-home-lifecycle-api") return apiModule;
      if (id === "\0magic-home-lifecycle-icon") return `import React from "react"; export function Icon(){ return React.createElement("span"); }`;
    },
  }],
});
after(async () => {
  await vite.close();
  dom.window.close();
  globalThis.setTimeout = nativeSetTimeout;
  globalThis.clearTimeout = nativeClearTimeout;
});

function deferred() {
  let resolve;
  const promise = new Promise((yes) => { resolve = yes; });
  return { promise, resolve };
}

async function mount(MagicClassHome) {
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  function LocationProbe() {
    const location = useLocation();
    const navigate = useNavigate();
    globalThis.__magicHomeLocation = `${location.pathname}${location.search}`;
    globalThis.__magicHomeNavigate = navigate;
    return createElement("output", { "data-testid": "location" }, `${location.pathname}${location.search}`);
  }
  await act(async () => root.render(createElement(StrictMode, null,
    createElement(MemoryRouter, { initialEntries: ["/home"] },
      createElement(LocationProbe),
      createElement(Routes, null,
        createElement(Route, { path: "/home", element: createElement(MagicClassHome, {
          courses: [{ id: "course-1", name: "课程一" }],
          fusion: { state: "ready", capabilities: ["workspace", "generation"] },
          providerStatus: { providers: { llm: true } },
        }) }),
        createElement(Route, { path: "/courses/:courseId/workspaces/:workspaceId", element: createElement("div", { "data-testid": "destination" }, "课堂已打开") }),
        createElement(Route, { path: "/away", element: createElement("div", { "data-testid": "away" }, "已离开学习页") }),
        createElement(Route, { path: "*", element: createElement("div", { "data-testid": "unexpected" }, "未知路由") }),
      ),
    ),
  )));
  return {
    host,
    async go(path) { await act(async () => globalThis.__magicHomeNavigate(path)); },
    async unmount() {
      await act(async () => root.unmount());
      host.remove();
      globalThis.__magicHomeNavigate = null;
    },
  };
}

async function submitTopic(host) {
  const textarea = host.querySelector("textarea[aria-label='学习主题']");
  await act(async () => Simulate.change(textarea, { target: { value: "学习线性代数" } }));
  await act(async () => host.querySelector("form").dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true })));
}

test("unmount cancels the scheduled job poll under StrictMode", async () => {
  const poll = deferred();
  let pollCalls = 0;
  globalThis.__magicHomeLifecycleApi = {
    generateMagicClassHome: async () => ({ workspace_id: "ws-1", job: { id: "job-1", status: "queued" } }),
    getMagicClassJob() { pollCalls += 1; return poll.promise; },
  };
  const { default: MagicClassHome } = await vite.ssrLoadModule("/src/components/magicclass/magicclassHome.jsx");
  const view = await mount(MagicClassHome);
  try {
    await submitTopic(view.host);
    assert.equal(pollCalls, 1, "the job is polled once after a successful generation request");
    await act(async () => poll.resolve({ status: "running", step: "drafting" }));
    assert.equal(pendingPollTimers.size, 1, "the existing 800ms polling interval is scheduled");

    await view.go("/away");
    assert.equal(pendingPollTimers.size, 0, "unmount clears the pending poll timer");
    await act(async () => new Promise((resolve) => nativeSetTimeout(resolve, 820)));
    assert.equal(pollCalls, 1, "the stopped polling loop does not issue another request");
    assert.equal(view.host.querySelector("[data-testid='location']").textContent, "/away");
  } finally {
    await view.unmount();
    delete globalThis.__magicHomeLifecycleApi;
  }
});

test("a generation request sent before unmount cannot start polling when its response arrives late", async () => {
  const generation = deferred();
  let generationCalls = 0;
  let pollCalls = 0;
  globalThis.__magicHomeLifecycleApi = {
    generateMagicClassHome() { generationCalls += 1; return generation.promise; },
    getMagicClassJob() { pollCalls += 1; return Promise.resolve({ status: "completed" }); },
  };
  const { default: MagicClassHome } = await vite.ssrLoadModule("/src/components/magicclass/magicclassHome.jsx");
  const view = await mount(MagicClassHome);
  try {
    await submitTopic(view.host);
    assert.equal(generationCalls, 1, "the submit event sends exactly one generation request");
    assert.equal(view.host.querySelector("button[type='submit']").disabled, true, "the form reflects its busy state while generation is pending");

    await view.go("/away");
    await act(async () => generation.resolve({ workspace_id: "ws-1", job: { id: "job-1", status: "queued" } }));
    assert.equal(pollCalls, 0, "a stale generate response cannot begin polling after navigation");
    assert.equal(view.host.querySelector("[data-testid='location']").textContent, "/away", "the stale generate response cannot navigate back");
  } finally {
    await view.unmount();
    delete globalThis.__magicHomeLifecycleApi;
  }
});

test("a newer submit keeps its own token when two submits start in one render cycle", async () => {
  const generations = [deferred(), deferred()];
  const job = deferred();
  let generationCalls = 0;
  let pollCalls = 0;
  globalThis.__magicHomeLifecycleApi = {
    generateMagicClassHome() {
      const current = generationCalls++;
      return generations[current].promise;
    },
    getMagicClassJob() { pollCalls += 1; return job.promise; },
  };
  const { default: MagicClassHome } = await vite.ssrLoadModule("/src/components/magicclass/magicclassHome.jsx");
  const view = await mount(MagicClassHome);
  try {
    const textarea = view.host.querySelector("textarea[aria-label='学习主题']");
    await act(async () => Simulate.change(textarea, { target: { value: "学习线性代数" } }));
    await act(async () => {
      const form = view.host.querySelector("form");
      form.dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true }));
      form.dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true }));
    });
    assert.equal(generationCalls, 2, "both submit events reached the API before React committed busy state");
    assert.equal(view.host.querySelector("button[type='submit']").disabled, true);

    await act(async () => generations[1].resolve({ workspace_id: "ws-new", job: { id: "job-new", status: "queued" } }));
    assert.equal(pollCalls, 1, "the newer generation proceeds to its own job poll");
    await act(async () => generations[0].resolve({ workspace_id: "ws-old", job: { id: "job-old", status: "completed" } }));
    assert.equal(globalThis.__magicHomeLocation, "/home", "the older completed generation cannot navigate over the newer one");
    assert.equal(view.host.querySelector("button[type='submit']").disabled, true, "the older request cannot clear the newer request's busy state");
  } finally {
    await view.unmount();
    await act(async () => job.resolve({ status: "running" }));
    delete globalThis.__magicHomeLifecycleApi;
  }
});

test("a job response arriving after unmount cannot navigate, while a current completed job still navigates", async () => {
  const lateJob = deferred();
  let pollCalls = 0;
  let generationCalls = 0;
  globalThis.__magicHomeLifecycleApi = {
    generateMagicClassHome() {
      generationCalls += 1;
      return Promise.resolve({ workspace_id: "ws-1", job: { id: "job-1", status: "queued" } });
    },
    getMagicClassJob() { pollCalls += 1; return lateJob.promise; },
  };
  const { default: MagicClassHome } = await vite.ssrLoadModule("/src/components/magicclass/magicclassHome.jsx");
  const view = await mount(MagicClassHome);
  try {
    await submitTopic(view.host);
    assert.equal(generationCalls, 1);
    assert.equal(pollCalls, 1, "the job request is actually in flight before unmount");
    assert.equal(view.host.querySelector("button[type='submit']").disabled, true);
    await view.go("/away");
    await act(async () => lateJob.resolve({ status: "completed" }));
    assert.equal(globalThis.__magicHomeLocation, "/away", "the late job response cannot navigate back after its page unmounts");
    assert.ok(view.host.querySelector("[data-testid='away']"));
  } finally {
    await view.unmount();
    delete globalThis.__magicHomeLifecycleApi;
  }

  globalThis.__magicHomeLifecycleApi = {
    generateMagicClassHome: async () => ({ workspace_id: "ws-1", job: { id: "job-2", status: "queued" } }),
    getMagicClassJob: async () => { pollCalls += 1; return { status: "completed" }; },
  };
  const completedView = await mount(MagicClassHome);
  try {
    await submitTopic(completedView.host);
    assert.equal(pollCalls, 2, "the current generation polls and receives its completed status");
    assert.equal(completedView.host.querySelector("[data-testid='location']").textContent, "/courses/course-1/workspaces/ws-1?mode=playback");
    assert.ok(completedView.host.querySelector("[data-testid='destination']"), "successful completion keeps its classroom navigation");
  } finally {
    await completedView.unmount();
    delete globalThis.__magicHomeLifecycleApi;
  }
  delete globalThis.__magicHomeLocation;
});
