import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { createSSRApp } from "vue";
import { renderToString } from "vue/server-renderer";
import { createMemoryHistory, createRouter } from "vue-router";
import { createServer } from "vite";
import { readFile } from "node:fs/promises";

let vite;

function installBrowserStubs() {
  globalThis.localStorage = {
    getItem() { return null; },
    setItem() {},
    removeItem() {},
  };
  globalThis.window = {
    history: { state: null, length: 1, replaceState() {}, pushState() {}, go() {} },
    location: { protocol: "http:", host: "localhost", pathname: "/", search: "", hash: "", href: "http://localhost/", assign() {}, replace() {} },
    addEventListener() {},
    removeEventListener() {},
    setTimeout,
  };
  globalThis.location = globalThis.window.location;
  globalThis.document = {
    addEventListener() {},
    removeEventListener() {},
    querySelector() { return null; },
    visibilityState: "visible",
  };
}

before(async () => {
  installBrowserStubs();
  vite = await createServer({ appType: "custom", logLevel: "silent", server: { middlewareMode: true } });
});

after(async () => {
  await vite?.close();
});

test("registers the student chaoxing page", async () => {
  const { default: router } = await vite.ssrLoadModule("/src/router.js");
  const studentRoute = router.getRoutes().find((route) => route.path === "/profile/chaoxing");

  assert.equal(studentRoute?.name, "student-chaoxing");
  assert.equal(router.resolve("/profile/chaoxing").matched.at(-1)?.name, "student-chaoxing");
});

test("renders the student chaoxing connection screen", async () => {
  const { default: ChaoxingView } = await vite.ssrLoadModule(
    "/src/views/student/StudentChaoxingView.vue",
  );
  const html = await renderToString(createSSRApp(ChaoxingView));

  assert.match(html, /学习通同步/);
  assert.match(html, /同账号多端同步/);
});

test("renders a learning-platform entry on the notifications page", async () => {
  const { default: NotificationsView } = await vite.ssrLoadModule(
    "/src/views/student/StudentNotificationsView.vue",
  );
  const app = createSSRApp(NotificationsView);
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/", component: { template: "<div />" } }],
  });
  app.use(router);
  await router.push("/");
  await router.isReady();
  const html = await renderToString(app);

  assert.match(html, /管理学习通|连接学习通/);
});

test("normalizes unified notices without making them announcement receipts", async () => {
  const { normalizeNoticeItems, safeNoticeSourceUrl, shouldMarkAnnouncementRead } = await vite.ssrLoadModule(
    "/src/services/noticeFeed.js",
  );
  const [notice] = normalizeNoticeItems({
    items: [{ id: "n1", title: "学习通通知", kind: "unified", unread: false, time: "2026-08-13T10:00:00Z" }],
  });

  assert.equal(notice.has_read, true);
  assert.equal(notice.published_at, "2026-08-13T10:00:00Z");
  assert.equal(shouldMarkAnnouncementRead(notice), false);
  assert.equal(shouldMarkAnnouncementRead({ kind: "announcement", has_read: false }), true);
  assert.equal(safeNoticeSourceUrl({ kind: "unified", source_url: "javascript:alert(1)" }), null);
  assert.equal(
    safeNoticeSourceUrl({ kind: "unified", source_url: "https://example.test/notice/1" }),
    "https://example.test/notice/1",
  );
});

test("shows synced learning-platform notices in the default feed", async () => {
  const { noticeMatchesFilters } = await vite.ssrLoadModule("/src/services/noticeFeed.js");
  const notice = {
    title: "学习通课程通知",
    content: "请查看新的课程安排",
    source: "chaoxing",
    kind: "unified",
    has_read: true,
  };

  assert.equal(noticeMatchesFilters(notice, { source: "all", readFilter: "all", query: "" }), true);
  assert.equal(noticeMatchesFilters(notice, { source: "all", readFilter: "all", query: "课程" }), true);
});

test("does not refresh the Campus token for downstream chaoxing authentication errors", async () => {
  const source = await readFile(new URL("../src/services/api.js", import.meta.url), "utf8");
  assert.match(source, /_isDownstreamChaoxingAuthError\(error\)/);
  assert.match(source, /detail === "reauth_required"/);
  assert.doesNotMatch(source, /!original\.url\?\.includes\("\/chaoxing\/"\)/);
});
