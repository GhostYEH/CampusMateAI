import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { createSSRApp } from "vue";
import { renderToString } from "vue/server-renderer";
import { createServer } from "vite";

let vite;

before(async () => {
  vite = await createServer({
    appType: "custom",
    logLevel: "silent",
    server: { middlewareMode: true },
  });
});

after(async () => {
  await vite?.close();
});

test("renders a hot post with its interaction counts", async () => {
  const { default: CampusHotPostsPanel } = await vite.ssrLoadModule(
    "/src/components/CampusHotPostsPanel.vue",
  );
  const html = await renderToString(
    createSSRApp(CampusHotPostsPanel, {
      posts: [{
        id: "post-1",
        title: "图书馆座位攻略",
        category: "campus",
        like_count: 12,
        comment_count: 3,
        created_at: "2026-08-18T09:00:00Z",
      }],
    }),
  );

  assert.match(html, /图书馆座位攻略/);
  assert.match(html, /12/);
  assert.match(html, /3/);
});
