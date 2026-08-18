import assert from "node:assert/strict";
import { test } from "node:test";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("AI campus assistant exposes the screenshot-matched workspace and working controls", async () => {
  const [view, shell, css] = await Promise.all([
    readFile(path.join(webRoot, "src", "views", "student", "StudentCounselorView.vue"), "utf8"),
    readFile(path.join(webRoot, "src", "views", "AppShell.vue"), "utf8"),
    readFile(path.join(webRoot, "src", "styles", "counselor-reference.css"), "utf8"),
  ]);

  assert.match(view, /AI校园助手/);
  assert.match(view, /你的专属校园智能伙伴/);
  assert.match(view, /会话记录/);
  assert.match(view, /校园办事帮助/);
  assert.match(view, /我是 CampusMate AI/);
  assert.match(view, /@keydown\.enter\.exact\.prevent="send\(\)"/);
  assert.match(view, /@click="send\(question\)"/);
  assert.match(view, /function openService\(item\)/);
  assert.match(view, /@click="openService\(item\)"/);
  assert.match(view, /counselor-campus-hero-reference\.png/);
  assert.match(shell, /'counselor-mode': route\.path === ['"]\/counselor['"]/);
  assert.match(css, /grid-template-columns:\s*minmax\(274px,300px\)\s+minmax\(0,1fr\)\s+minmax\(310px,347px\)/);

  const layout = await readFile(path.join(webRoot, "src", "styles", "layout-system.css"), "utf8");
  assert.match(layout, /--sidebar-width:\s*282px/);
  assert.match(layout, /--header-height:\s*85px/);
  assert.match(layout, /grid-template-columns:\s*var\(--sidebar-width\)/);
});
