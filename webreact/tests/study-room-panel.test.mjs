/**
 * 回归：StudyRoomPanel 接收 `open`，但通用 Modal 没有 `open` 参数。
 *
 * 未打开时组件必须什么都不渲染；否则弹窗会在进入专注页时自动盖住整页，
 * 且关闭按钮只改外部状态、无法移除弹窗。旧实现会无条件进入 Modal，
 * 因此这里的 SSR 渲染会直接失败。
 */
import test, { after } from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import { fileURLToPath } from "node:url";

const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true, watch: null },
  appType: "custom",
  logLevel: "silent",
});
after(async () => { await vite.close(); });

const { default: StudyRoomPanel } = await vite.ssrLoadModule(
  "/src/components/study/StudyRoomPanel.jsx",
);

test("closed study room panel renders nothing", () => {
  const html = renderToStaticMarkup(
    createElement(StudyRoomPanel, { open: false, onClose() {} }),
  );
  assert.equal(html, "");
});
