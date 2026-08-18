import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { createSSRApp } from "vue";
import { renderToString } from "vue/server-renderer";
import { createServer } from "vite";

let vite;
before(async () => { vite = await createServer({ appType: "custom", logLevel: "silent", server: { middlewareMode: true } }); });
after(async () => { await vite?.close(); });

for (const [modulePath, phrases] of [
  ["/src/views/student/StudentUniversityView.vue", ["我的大学", "搜索大学", "切换大学后"]],
  ["/src/views/student/StudentCommunityView.vue", ["校园论坛", "发布帖子", "暂无帖子"]],
  ["/src/views/student/StudentAcademicView.vue", ["教务系统", "暂未支持自动教务同步", "不会保存在浏览器"]],
]) {
  test(`renders V3 core state copy for ${modulePath}`, async () => {
    const { default: View } = await vite.ssrLoadModule(modulePath);
    const html = await renderToString(createSSRApp(View));
    for (const phrase of phrases) assert.match(html, new RegExp(phrase));
  });
}
