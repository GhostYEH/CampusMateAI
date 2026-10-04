import test, { after, afterEach } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { createServer } from "vite";
import { fileURLToPath } from "node:url";

const dom = new JSDOM("<!doctype html><html><body></body></html>", { url: "http://localhost" });
globalThis.window = dom.window; globalThis.document = dom.window.document;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true, watch: null }, appType: "custom", logLevel: "silent",
  plugins: [{
    name: "agent-run-hook-doubles", enforce: "pre",
    resolveId(source, importer) {
      if (!importer?.endsWith("/hooks/useAgentRun.js")) return;
      if (source === "../data/agentRuntimeApi.js") return "\0run-api";
      if (source === "./useAgentSse.js") return "\0run-sse";
    },
    load(id) {
      if (id === "\0run-api") return "export const getAgentRun = (...args) => globalThis.__runApi(...args);";
      if (id === "\0run-sse") return "export function useAgentSse(options) { globalThis.__runEvent = options.onEvent; return { status: 'idle', cancel() {} }; }";
    },
  }],
});
const { useAgentRun } = await vite.ssrLoadModule("/src/hooks/useAgentRun.js");
after(async () => { await vite.close(); dom.window.close(); });
afterEach(() => { delete globalThis.__runApi; delete globalThis.__runEvent; });
function deferred() {
  let resolve; const promise = new Promise((yes) => { resolve = yes; });
  return { promise, resolve };
}
function snapshot(runId, status = "RUNNING") { return { run_id: runId, status, artifact_ids: [] }; }
let latest;
function Probe({ runId }) { latest = useAgentRun({ runId }); return createElement("div", null, latest.run?.run_id || "loading"); }
async function mount(runId) {
  const host = document.createElement("div"); document.body.append(host); const root = createRoot(host);
  await act(async () => root.render(createElement(Probe, { runId })));
  return { host, root, close: async () => { await act(async () => root.unmount()); host.remove(); } };
}

test("a terminal run without artifacts performs one supplementary fetch instead of a loop", async () => {
  let calls = 0;
  globalThis.__runApi = async (runId) => {
    assert.ok(++calls <= 3, "terminal fetch must be bounded");
    return snapshot(runId, "SUCCEEDED");
  };
  const view = await mount("finished");
  try {
    assert.equal(calls, 2);
    assert.equal(latest.isTerminal, true);
    await act(async () => view.root.render(createElement(Probe, { runId: "finished" })));
    assert.equal(calls, 2, "a new empty artifact array must not restart the effect");
  } finally { await view.close(); }
});

test("switching runs drops late GET results and events from the previous run", async () => {
  const old = deferred(); const current = deferred();
  globalThis.__runApi = (runId) => runId === "old" ? old.promise : current.promise;
  const view = await mount("old");
  try {
    await act(async () => view.root.render(createElement(Probe, { runId: "current" })));
    await act(async () => old.resolve(snapshot("old")));
    assert.equal(latest.loading, true);
    assert.equal(latest.run, null);
    await act(async () => current.resolve(snapshot("current")));
    await act(async () => globalThis.__runEvent({ run_id: "old", sequence: 1, status: "FAILED" }));
    assert.equal(latest.run.run_id, "current");
    assert.equal(latest.run.status, "RUNNING");
    assert.equal(latest.events.length, 0);
    await act(async () => globalThis.__runEvent({ run_id: "current", sequence: 1, artifact_id: "artifact" }));
    assert.deepEqual(latest.run.artifact_ids, ["artifact"]);
    assert.equal(latest.events.length, 1);
  } finally { await view.close(); }
});
