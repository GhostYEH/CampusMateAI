import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const reactRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const read = (file) => readFile(path.join(reactRoot, file), "utf8");

const AGENT_ENTRIES = [
  ["期末复习", "/agent/final-review"],
  ["课程研究", "/agent/course-research"],
  ["通知事务", "/agent/notice-workflow"],
];

test("React home hero exposes the three agent workbench entries", async () => {
  const hero = await read("src/pages/home/SylvaCampusOverview.jsx");

  for (const [label, href] of AGENT_ENTRIES) {
    assert.match(hero, new RegExp(href.replace(/\//g, "\\/")), `缺少入口路径 ${href}`);
    assert.match(hero, new RegExp(`label: "${label}"`), `缺少入口文案 ${label}`);
  }
  assert.match(hero, /className="sylva-agent-entry"/);
  assert.match(hero, /onNavigate\?\.\(entry\.path\)/);
  // 入口必须渲染成 <button> 而非 <a>,否则走的是路由跳变而不是 SPA 导航
  assert.match(hero, /<button\b[\s\S]*className="sylva-agent-entry"/);
});

test("React home actually mounts the hero with a working navigate handler", async () => {
  const homePage = await read("src/pages/HomePage.jsx");

  assert.match(homePage, /import SylvaCampusOverview/);
  assert.match(homePage, /<SylvaCampusOverview/);
  assert.match(homePage, /onNavigate=\{handleNavigate\}/);
  assert.match(homePage, /function handleNavigate\(path\) \{ navigate\(path\); \}/);
});

test("React app registers the agent workbench routes", async () => {
  const app = await read("src/App.jsx");

  for (const [, href] of AGENT_ENTRIES) {
    assert.match(app, new RegExp(`path="${href.replace(/\//g, "\\/")}"`), `缺少路由 ${href}`);
  }
});

test("React footer links every agent workbench", async () => {
  const footer = await read("src/components/HomeFooter.jsx");

  assert.match(footer, /Agent 工作台/);
  for (const [label, href] of AGENT_ENTRIES) {
    assert.match(footer, new RegExp(`\\["${label}", "${href.replace(/\//g, "\\/")}"\\]`), `页脚缺少 ${label}`);
  }
});

test("agent entry row keeps a clickable and non-overflowing layout", async () => {
  const css = await read("src/styles/sylva-home.css");

  assert.match(css, /\.sylva-agent-entry \{/);
  assert.match(css, /\.sylva-agent-entry \{[^}]*cursor: pointer/);
  // 入口与首屏主按钮同排,容器必须换行,否则窄屏会溢出
  assert.match(css, /\.sylva-overview-actions \{[^}]*flex-wrap: wrap/);
});
