import test, { after } from "node:test";
import assert from "node:assert/strict";

import "./helpers/setup-globals.mjs";
import { parseHTML } from "linkedom";

const { window, document } = parseHTML("<!doctype html><html><body></body></html>");
globalThis.window = window;
globalThis.document = document;
Object.defineProperty(globalThis, "navigator", { value: window.navigator, configurable: true, writable: true });
globalThis.HTMLElement = window.HTMLElement;
globalThis.Element = window.Element;
globalThis.Node = window.Node;
globalThis.Event = window.Event;
globalThis.MutationObserver = window.MutationObserver;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
window.matchMedia ||= () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
globalThis.matchMedia = window.matchMedia;

const apiModule = await import("../src/data/api.js");
const { createMockClient } = await import("./helpers/mock-client.mjs");
const mock = createMockClient(apiModule.client);
const { createServer } = await import("vite");
const { fileURLToPath } = await import("node:url");
const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true, watch: null },
  appType: "custom",
  logLevel: "silent",
});
after(async () => {
  await Promise.race([vite.close(), new Promise((resolve) => setTimeout(resolve, 5000).unref?.())]);
});

const React = (await import("react")).default;
const { createRoot } = await import("react-dom/client");
const { MemoryRouter } = await import("react-router-dom");
const { default: WorkspacePanel } = await vite.ssrLoadModule("/src/components/magicclass/WorkspacePanel.jsx");
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

test("list reload does not invalidate an in-flight expanded workspace stages request", async () => {
  const courseId = "crs_panel_epoch";
  const workspaceId = "ws_panel_epoch";
  const listUrl = `/courses/${courseId}/workspaces`;
  const stagesUrl = `/courses/${courseId}/workspaces/${workspaceId}/stages`;
  mock.onGet(listUrl, {
    items: [{ id: workspaceId, course_id: courseId, name: "现有工作台", revision: 1 }],
    next_cursor: null,
  });
  mock.onGet(stagesUrl, () => new Promise((resolve) => {
    globalThis.releasePanelStages = () => resolve({
      status: 200,
      data: { items: [{ id: "stg_panel_epoch", workspace_id: workspaceId, title: "应保留的场景", revision: 1 }] },
      headers: {},
    });
  }));
  mock.onPost(`/courses/${courseId}/workspaces`, {
    id: "ws_new_panel_epoch", course_id: courseId, name: "触发列表回读", revision: 1,
  });
  mock.onDelete(`/courses/${courseId}/workspaces/${workspaceId}`, {});

  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await React.act(async () => {
    root.render(React.createElement(MemoryRouter, null, React.createElement(WorkspacePanel, {
      courseId,
      courseName: "生命周期验收",
      canEdit: true,
    })));
  });
  for (let i = 0; i < 40 && !host.querySelector(".magicclass-workspace-item"); i += 1) {
    await React.act(async () => { await flush(); });
  }
  const contentButton = [...host.querySelectorAll("button")].find((button) => button.textContent.trim() === "内容");
  assert.ok(contentButton, "the workspace must be mounted before loading its stages");
  await React.act(async () => { contentButton.dispatchEvent(new window.Event("click", { bubbles: true })); });
  for (let i = 0; i < 40 && !globalThis.releasePanelStages; i += 1) await flush();
  assert.equal(typeof globalThis.releasePanelStages, "function", "the stages request should be in flight");

  const deleteButton = [...host.querySelectorAll("button")].find((button) => button.textContent.trim() === "删除");
  assert.ok(deleteButton && !deleteButton.disabled, "the list reload trigger must be available during stage loading");
  await React.act(async () => { deleteButton.dispatchEvent(new window.Event("click", { bubbles: true })); await flush(); });
  for (let i = 0; i < 40 && mock.requests.filter((request) => request.url === listUrl).length < 2; i += 1) {
    await React.act(async () => { await flush(); });
  }
  assert.equal(mock.requests.filter((request) => request.url === listUrl).length, 2, "deleting a workspace must start a list reload");

  await React.act(async () => { globalThis.releasePanelStages(); await flush(); });
  assert.match(host.textContent, /应保留的场景/, "the independent stages response must remain current across list reload");
  await React.act(async () => root.unmount());
  host.remove();
  delete globalThis.releasePanelStages;
});

test("a delete finishing after a course switch cannot update or reload the new course panel", async () => {
  const courseA = "crs_panel_old";
  const courseB = "crs_panel_new";
  const workspaceId = "ws_panel_old";
  const listA = `/courses/${courseA}/workspaces`;
  const listB = `/courses/${courseB}/workspaces`;
  mock.onGet(listA, { items: [{ id: workspaceId, course_id: courseA, name: "旧课程工作台", revision: 1 }], next_cursor: null });
  mock.onGet(listB, { items: [{ id: "ws_new", course_id: courseB, name: "新课程工作台", revision: 1 }], next_cursor: null });
  let releaseDelete;
  let markDeleteStarted;
  const deleteStarted = new Promise((resolve) => { markDeleteStarted = resolve; });
  mock.onDelete(`/courses/${courseA}/workspaces/${workspaceId}`, (config) => new Promise((resolve) => {
    releaseDelete = () => resolve({ status: 200, data: {}, config, headers: {} });
    markDeleteStarted();
  }));

  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  const renderCourse = async (courseId) => React.act(async () => {
    root.render(React.createElement(MemoryRouter, null, React.createElement(WorkspacePanel, { courseId })));
  });
  await renderCourse(courseA);
  for (let i = 0; i < 40 && !host.textContent.includes("旧课程工作台"); i += 1) {
    await React.act(async () => { await flush(); });
  }
  const deleteButton = [...host.querySelectorAll("button")].find((button) => button.textContent.trim() === "删除");
  assert.ok(deleteButton, "old course panel should render before starting its mutation");
  await React.act(async () => { deleteButton.dispatchEvent(new window.Event("click", { bubbles: true })); });
  await deleteStarted;

  await renderCourse(courseB);
  for (let i = 0; i < 40 && !host.textContent.includes("新课程工作台"); i += 1) {
    await React.act(async () => { await flush(); });
  }
  const oldListReads = mock.requests.filter((request) => request.url === listA).length;
  releaseDelete();
  await React.act(async () => { await flush(); });
  assert.equal(mock.requests.filter((request) => request.url === listA).length, oldListReads,
    "the old course mutation must not start a stale list reload");
  assert.doesNotMatch(host.textContent, /已删除「旧课程工作台」/,
    "the old course mutation must not write a notice into the new course view");
  assert.match(host.textContent, /新课程工作台/);
  await React.act(async () => root.unmount());
  host.remove();
});
