import test, { after } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { Simulate } from "react-dom/test-utils";
import { createServer } from "vite";
import { fileURLToPath } from "node:url";

const dom = new JSDOM("<!doctype html><html><body></body></html>", { url: "http://localhost", pretendToBeVisual: true });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true, watch: null }, appType: "custom", logLevel: "silent",
  plugins: [{
    name: "searchbox-race-doubles", enforce: "pre",
    resolveId(source, importer) {
      if (source === "../data/api.js" && importer?.includes("/components/AppShell.jsx")) return "\0search-api";
      if (source === "../data/contracts.js" && importer?.includes("/components/AppShell.jsx")) return "\0search-contracts";
      if (source === "open-glass-ui") return "\0search-ui";
      const shellMocks = {
        "../app/AppContext.jsx": "search-context",
        "../app/routePreload.js": "search-preload",
        "../app/shellMode.js": "search-mode",
        "./SmoothCursor.jsx": "search-noop",
        "./GlassSurface.jsx": "search-glass",
        "./Icon.jsx": "search-icon",
        "./FloatingNav/FloatingNav.jsx": "search-noop",
        "./VisualEffectBoundary.jsx": "search-boundary",
        "../features/study/scenes.js": "search-scenes",
      };
      if (shellMocks[source] && importer?.includes("/components/AppShell.jsx")) return `\0${shellMocks[source]}`;
    },
    load(id) {
      if (id === "\0search-api") return `
        const api = () => globalThis.__searchApi;
        export const getCourses = (...args) => api().getCourses(...args);
        export const getAssignments = (...args) => api().getAssignments(...args);
      `;
      if (id === "\0search-contracts") return `export const itemsOf = (value) => Array.isArray(value) ? value : value?.items || [];`;
      if (id === "\0search-ui") return `import React from "react";
        export function SearchField({ value, onValueChange, ...props }) { return React.createElement("input", { ...props, value, onChange: (event) => onValueChange(event.target.value) }); }
        export function Avatar(){return null} export function IconButton(props){return React.createElement("button", props)}
      `;
      if (id === "\0search-context") return `export function useApp(){return {session:null,unreadCount:0,pendingCount:0,reduceMotion:true}}`;
      if (id === "\0search-preload") return `export function preloadRoute(){}`;
      if (id === "\0search-mode") return `export function isMagicClassImmersivePath(){return false}`;
      if (id === "\0search-noop") return `export default function Noop(){return null}`;
      if (id === "\0search-glass") return `import React from "react"; export default function Glass({children,className,role,...props}){return React.createElement("div",{className,role,"aria-label":props["aria-label"]},children)}`;
      if (id === "\0search-icon") return `export function Icon(){return null}`;
      if (id === "\0search-boundary") return `import React from "react"; export default function Boundary({children}){return React.createElement(React.Fragment,null,children)}`;
      if (id === "\0search-scenes") return `export function readStudyScene(){return "default"} export const STUDY_SCENE_ASSETS={default:""}`;
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

async function delay() { await act(async () => new Promise((resolve) => setTimeout(resolve, 240))); }

test("search ignores older success and failure, and short queries clear in-flight UI", async () => {
  const calls = [];
  globalThis.__searchApi = {
    getCourses() { const request = deferred(); calls.push({ kind: "course", request }); return request.promise; },
    getAssignments() { const request = deferred(); calls.push({ kind: "assignment", request }); return request.promise; },
  };
  const { SearchBox } = await vite.ssrLoadModule("/src/components/AppShell.jsx");
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  await act(async () => root.render(createElement(MemoryRouter, null, createElement(SearchBox))));
  const input = () => host.querySelector("input[name='global-search']");
  const setQuery = async (value) => act(async () => {
    const fiberKey = Object.keys(input()).find((key) => key.startsWith("__reactFiber$"));
    let fiber = input()[fiberKey];
    while (fiber && typeof fiber.memoizedProps?.onValueChange !== "function") fiber = fiber.return;
    assert.ok(fiber, "mounted SearchField exposes its user-change callback");
    fiber.memoizedProps.onValueChange(value);
  });
  const resolvePair = async (offset, course) => {
    await act(async () => {
      calls[offset].request.resolve([{ id: course.toLowerCase(), name: course }]);
      calls[offset + 1].request.resolve([]);
    });
  };
  try {
    await setQuery("ab");
    await delay();
    await setQuery("cd");
    await delay();
    assert.equal(calls.length, 4);
    await act(async () => calls[0].request.resolve([{ id: "ab", name: "AB stale" }]));
    await act(async () => calls[1].request.resolve([]));
    assert.match(host.textContent, /正在搜索…/, "old finally cannot clear the new query's loading state");
    await resolvePair(2, "CD current");
    assert.match(host.textContent, /CD current/);
    await act(async () => { calls[2].request.reject(new Error("old failure")); calls[3].request.resolve([]); });
    assert.match(host.textContent, /CD current/);
    assert.doesNotMatch(host.textContent, /AB stale/);

    await setQuery("ef");
    await delay();
    const oldStart = calls.length - 2;
    await setQuery("gh");
    await delay();
    const newStart = calls.length - 2;
    await act(async () => calls[oldStart].request.reject(new Error("stale failure")));
    await act(async () => calls[oldStart + 1].request.resolve([]));
    assert.match(host.textContent, /正在搜索…/, "old error/finally cannot settle a newer search");
    await resolvePair(newStart, "GH current");
    assert.match(host.textContent, /GH current/);

    await setQuery("ij");
    await delay();
    const shortQueryOldStart = calls.length - 2;
    await setQuery("x");
    assert.equal(host.querySelector(".search-results"), null, "short query clears the results panel immediately");
    await act(async () => { calls[shortQueryOldStart].request.resolve([{ id: "ij", name: "IJ stale late" }]); calls[shortQueryOldStart + 1].request.resolve([]); });
    assert.equal(host.querySelector(".search-results"), null);
  } finally {
    await act(async () => root.unmount());
    host.remove();
    delete globalThis.__searchApi;
  }
});
