import test, { after } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { createServer } from "vite";
import { fileURLToPath } from "node:url";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "http://localhost",
  pretendToBeVisual: true,
});
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame.bind(dom.window);
globalThis.cancelAnimationFrame = dom.window.cancelAnimationFrame.bind(dom.window);

const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true, watch: null },
  appType: "custom",
  logLevel: "silent",
  plugins: [{
    name: "community-api-test-double",
    enforce: "pre",
    resolveId(source, importer) {
      if (source === "../data/api.js" && importer?.endsWith("/pages/CommunityPage.jsx")) {
        return "\0community-api-test-double";
      }
    },
    load(id) {
      if (id !== "\0community-api-test-double") return null;
      return `
        const api = () => globalThis.__communityTestApi;
        export const getCommunityCategories = (...args) => api().getCommunityCategories(...args);
        export const getCommunityPosts = (...args) => api().getCommunityPosts(...args);
        export const likePost = (...args) => api().likePost(...args);
        export const unlikePost = (...args) => api().unlikePost(...args);
        export const favoritePost = (...args) => api().favoritePost(...args);
        export const unfavoritePost = (...args) => api().unfavoritePost(...args);
        export const reportPost = (...args) => api().reportPost(...args);
        export const resolveAssetUrl = (value) => value;
      `;
    },
  }],
});
after(async () => { await vite.close(); dom.window.close(); });

function deferred() {
  let resolve;
  const promise = new Promise((yes) => { resolve = yes; });
  return { promise, resolve };
}

async function flush() {
  await act(async () => new Promise((resolve) => window.setTimeout(resolve, 240)));
}

test("community pagination uses its target page and drops page results after filters change", async () => {
  const initial = deferred();
  const secondPage = deferred();
  const stalePage = deferred();
  const filtered = deferred();
  const likes = { first: deferred(), second: deferred() };
  const calls = [];
  globalThis.__communityTestApi = {
    getCommunityCategories: async () => ({ items: [] }),
    getCommunityPosts(params) {
      calls.push(params);
      if (calls.length === 1) return initial.promise;
      if (params.page === 2) return secondPage.promise;
      if (params.page === 3) return stalePage.promise;
      return filtered.promise;
    },
    likePost: (id) => likes[id].promise,
    unlikePost: async (item) => item,
    favoritePost: async (item) => item,
    unfavoritePost: async (item) => item,
    reportPost: async () => ({}),
  };

  const { default: CommunityPage } = await vite.ssrLoadModule("/src/pages/CommunityPage.jsx");
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  await act(async () => root.render(createElement(MemoryRouter, null, createElement(CommunityPage))));

  try {
    await flush();
    assert.equal(calls[0].page, 1);
    await act(async () => initial.resolve({ items: [
      { id: "first", title: "第一页帖子", content: "正文", liked: false, like_count: 0 },
      { id: "second", title: "第二帖", content: "正文", liked: false, like_count: 0 },
    ], total: 50 }));
    await act(async () => host.querySelector(".forum-load-more button").click());
    assert.equal(calls[1].page, 2, "load more must pass the incremented page directly");

    const likeButtons = host.querySelectorAll(".forum-card-foot button");
    await act(async () => { likeButtons[0].click(); likeButtons[4].click(); });
    await act(async () => likes.second.resolve({ id: "second", liked: true, like_count: 1 }));
    await act(async () => likes.first.resolve({ id: "first", liked: true, like_count: 1 }));
    assert.equal(host.querySelectorAll(".forum-load-more button").length, 0, "page two remains busy until its own request settles");
    await act(async () => secondPage.resolve({ items: [{ id: "third", title: "第二页帖子", content: "正文" }], total: 50 }));
    assert.equal(host.querySelectorAll(".forum-load-more button").length, 1, "a like must not strand pagination in its loading state");
    assert.equal(host.querySelectorAll(".forum-card-foot button.active").length, 2, "independent like responses both update their own posts");
    await act(async () => host.querySelector(".forum-load-more button").click());
    assert.equal(calls.at(-1).page, 3);

    await act(async () => host.querySelector(".hot-topic").click());
    await flush();
    assert.equal(calls.at(-1).page, 1);
    assert.equal(calls.at(-1).q, "图书馆占位技巧");

    await act(async () => filtered.resolve({ items: [{ id: "current", title: "新筛选结果", content: "当前" }], total: 1 }));
    await act(async () => stalePage.resolve({ items: [{ id: "stale", title: "旧分页结果", content: "旧" }], total: 50 }));

    assert.match(host.textContent, /新筛选结果/);
    assert.doesNotMatch(host.textContent, /旧分页结果/);
    assert.doesNotMatch(host.textContent, /第一页帖子/);
  } finally {
    await act(async () => root.unmount());
    host.remove();
    delete globalThis.__communityTestApi;
  }
});

test("community reset from page two requests page one and next pagination resumes at page two", async () => {
  const calls = [];
  globalThis.__communityTestApi = {
    getCommunityCategories: async () => ({ items: [] }),
    async getCommunityPosts(params) {
      calls.push(params);
      return { items: [{ id: `post-${params.page}`, title: `帖子${params.page}`, content: "正文" }], total: 10 };
    },
    likePost: async (id) => ({ id, liked: true, like_count: 1 }),
    unlikePost: async (item) => item,
    favoritePost: async (item) => item,
    unfavoritePost: async (item) => item,
    reportPost: async () => ({}),
  };
  const { default: CommunityPage } = await vite.ssrLoadModule("/src/pages/CommunityPage.jsx");
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  await act(async () => root.render(createElement(MemoryRouter, null, createElement(CommunityPage))));
  try {
    await flush();
    await act(async () => host.querySelector(".forum-load-more button").click());
    assert.equal(calls.at(-1).page, 2);
    await act(async () => host.querySelector(".forum-search").dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true })));
    assert.equal(calls.at(-1).page, 1, "form reset always requests the first page");
    await act(async () => host.querySelector(".forum-load-more button").click());
    assert.equal(calls.at(-1).page, 2, "pagination resumes from page two after reset");
  } finally {
    await act(async () => root.unmount());
    host.remove();
    delete globalThis.__communityTestApi;
  }
});
