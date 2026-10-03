import test, { after } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { act, createElement, StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import { fileURLToPath } from "node:url";
import { useAsyncResource } from "../src/hooks/useAsyncResource.js";

const dom = new JSDOM("<!doctype html><html><body></body></html>", { url: "http://localhost" });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true, watch: null },
  appType: "custom",
  logLevel: "silent",
});
after(async () => { await vite.close(); dom.window.close(); });

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

async function mount(load, key = "initial", strict = false) {
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  let latest;
  function Probe({ load, resourceKey }) {
    latest = useAsyncResource(load, [resourceKey]);
    return createElement("output", null, latest.loading ? "loading" : latest.error?.message || latest.data);
  }
  async function render(nextLoad, resourceKey) {
    const probe = createElement(Probe, { load: nextLoad, resourceKey });
    await act(async () => root.render(strict ? createElement(StrictMode, null, probe) : probe));
  }
  await render(load, key);
  return {
    get state() { return latest; },
    render,
    async unmount() { await act(async () => root.unmount()); host.remove(); },
  };
}

test("dependency changes keep the new result when an earlier request resolves late", async () => {
  const old = deferred(), current = deferred();
  const view = await mount(() => old.promise);
  try {
    await view.render(() => current.promise, "new");
    await act(async () => current.resolve("new result"));
    await act(async () => old.resolve("stale result"));
    assert.equal(view.state.data, "new result");
    assert.equal(view.state.loading, false);
  } finally { await view.unmount(); }
});

test("reload ignores a stale error and reads the current loader without changing dependencies", async () => {
  const old = deferred();
  const view = await mount(() => old.promise);
  try {
    await view.render(() => Promise.resolve("refreshed"), "initial");
    await act(async () => { await view.state.reload(); });
    await act(async () => old.reject(new Error("obsolete error")));
    assert.equal(view.state.data, "refreshed");
    assert.equal(view.state.error, null);
  } finally { await view.unmount(); }
});

test("synchronous loader failures become retryable resource errors", async () => {
  const view = await mount(() => { throw new Error("load failed"); });
  try {
    assert.equal(view.state.error.message, "load failed");
    assert.equal(view.state.loading, false);
    await view.render(() => Promise.resolve("recovered"), "initial");
    await act(async () => { await view.state.reload(); });
    assert.equal(view.state.data, "recovered");
    assert.equal(view.state.error, null);
  } finally { await view.unmount(); }
});

test("StrictMode's discarded request cannot overwrite the active mount", async () => {
  const first = deferred(), second = deferred();
  let calls = 0;
  const view = await mount(() => (++calls === 1 ? first.promise : second.promise), "initial", true);
  try {
    assert.equal(calls, 2);
    await act(async () => second.resolve("active mount"));
    await act(async () => first.resolve("discarded mount"));
    assert.equal(view.state.data, "active mount");
  } finally { await view.unmount(); }
});

test("unmount invalidates pending requests and retained reload callbacks", async () => {
  const pending = deferred();
  let calls = 0;
  const view = await mount(() => { calls += 1; return pending.promise; });
  const reload = view.state.reload;
  await view.unmount();
  await act(async () => pending.resolve("late"));
  await reload();
  assert.equal(calls, 1);
  assert.equal(view.state.data, null);
});

test("the extracted forecast section renders populated data and the empty fallback", async () => {
  const { ForecastSection } = await vite.ssrLoadModule("/src/components/learningState/StateOverview.jsx");
  const render = (forecasts) => renderToStaticMarkup(createElement(ForecastSection, { forecasts }));
  assert.match(render(null), /暂时没有未来预测数据/);
  assert.match(render({ items: [{ forecast_id: "f", forecast_type: "DEADLINE_COMPLETION_RISK", value: { pending_task_count: 3, risk_band: "HIGH" }, data_quality: "FRESH", confidence: 0.9 }] }), /待办 3.*风险 较高/);
});

test("the extracted goal center renders read-only annotations and run controls", async () => {
  const { GoalExecutionCenter } = await vite.ssrLoadModule("/src/components/learningState/GoalExecutionCenter.jsx");
  const markup = renderToStaticMarkup(createElement(GoalExecutionCenter, {
    goals: { items: [{ goal_id: "g", name: "复习" }] },
    plans: { items: [{ plan_id: "p", status: "PROPOSED" }] },
    jobs: [{ job_id: "j", job_kind: "learning_goal", latest_run_id: "r", status: "PAUSED" }],
    summary: { headline: "阶段总结", candidate_annotation: { available: false, reason: "MODEL_TIMEOUT" } },
  }));
  assert.match(markup, /候选模型响应超时/);
  assert.match(markup, /不会修改你的状态、计划或待办/);
  assert.match(markup, /恢复/);
});
