/**
 * P1-1 —— 内部服务地址 vs 浏览器公开课堂地址。
 *
 * 生产部署下两者必然不同：
 *   内部   http://magicclass:3000
 *   公开   https://classroom.example.edu
 *
 * 后端已修好"只下发公开地址"，但前端必须独立成立：
 * 即使后端某天下发了内部地址，前端也不得把它渲染成可打开的入口。
 */
import test, { after } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import "./helpers/setup-globals.mjs";

const REAL_FETCH = globalThis.fetch;

const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true },
  appType: "custom",
  logLevel: "silent",
});

after(async () => {
  globalThis.fetch = REAL_FETCH;
  await vite.close();
});

const { InteractiveClassroomView } = await vite.ssrLoadModule(
  "/src/components/interactive/InteractiveClassroomPanel.jsx",
);

const INTERNAL = "http://magicclass:3000";
const PUBLIC_ORIGIN = "https://classroom.example.edu";
const PUBLIC_URL = PUBLIC_ORIGIN + "/classroom/room_1";

const enabledStatus = (overrides = {}) => ({
  enabled: true,
  configured: true,
  available: true,
  unavailable: false,
  loading: false,
  compatibility: "compatible",
  degraded: false,
  unavailable_capabilities: [],
  service: "magicclass",
  version: "1.0.1",
  embed_origin: PUBLIC_ORIGIN,
  browser_embed_available: true,
  browser_embed_reason: null,
  external_3d_available: true,
  ...overrides,
});

const render = (props = {}) =>
  renderToStaticMarkup(
    createElement(InteractiveClassroomView, { status: enabledStatus(), ...props }),
  );

const escapeRe = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

test("Web 接受后端下发的公开课堂地址", () => {
  const markup = render({
    session: { session_id: "s1", status: "succeeded", step: "completed", url: PUBLIC_URL },
  });
  assert.match(markup, /<iframe/);
  assert.match(markup, new RegExp(escapeRe(PUBLIC_URL)));
});

test("Web 拒绝内部服务地址，绝不渲染成可打开入口", () => {
  const markup = render({
    session: {
      session_id: "s1",
      status: "succeeded",
      step: "completed",
      url: INTERNAL + "/classroom/room_1",
    },
  });
  assert.doesNotMatch(markup, /<iframe/, "内部地址绝不能渲染 iframe");
  assert.doesNotMatch(markup, /magicclass:3000/);
  assert.match(markup, /无法在此内嵌课堂/);
});

test("历史里只有内部地址时不提供任何打开入口", () => {
  const markup = render({
    items: [
      {
        session_id: "s1",
        mode: "explain",
        url: INTERNAL + "/classroom/room_1",
        url_unavailable_reason: "当前部署未开放浏览器访问",
      },
    ],
  });
  assert.doesNotMatch(markup, /magicclass:3000/);
  assert.match(markup, /待打开/);
});

test("已生成但未开放浏览器访问时给出明确提示，而不是回到重新生成", () => {
  const markup = render({
    status: enabledStatus({ embed_origin: null, browser_embed_available: false }),
    session: {
      session_id: "s1",
      status: "succeeded",
      step: "completed",
      url: null,
      classroom_id: "room_1",
    },
  });
  assert.match(markup, /课堂已生成，但当前部署未开放浏览器访问/);
  assert.doesNotMatch(markup, /<iframe/);
});

test("历史条目无法打开时展示原因", () => {
  const markup = render({
    items: [
      {
        session_id: "s1",
        mode: "explain",
        url: null,
        url_unavailable_reason: "当前部署未开放浏览器访问（未配置公开课堂地址）",
      },
    ],
  });
  assert.match(markup, /未配置公开课堂地址/);
});

test("不同端口 / 非 HTTPS 的课堂地址同样被拒绝", () => {
  for (const bad of [
    "https://classroom.example.edu:8443/classroom/room_1",
    "http://classroom.example.edu/classroom/room_1",
    "https://evil.example.com/classroom/room_1",
  ]) {
    const markup = render({
      session: { session_id: "s1", status: "succeeded", step: "completed", url: bad },
    });
    assert.doesNotMatch(markup, /<iframe/, "不应内嵌: " + bad);
    assert.match(markup, /无法在此内嵌课堂/);
  }
});
