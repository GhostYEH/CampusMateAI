/**
 * 导航栏「学习空间」契约。
 *
 * 学习空间是上游 OpenMAIC 应用以**独立进程、独立 Origin** 运行的那一份，由本站
 * 跨源内嵌。这条链路里最容易松掉的是 admission：后端一旦没配公开 Origin、
 * 或者公开 Origin 恰好等于本站，页面必须**不渲染 iframe**（fail-closed），
 * 而不是渲染一个空壳或退回内部地址。
 *
 * 因此这里钉三件事：
 * 1. 状态适配器打的是哪个端点；
 * 2. 各档后端状态下的 `ready` 与 blocker —— 尤其是"仍要渲染"的那些组合；
 * 3. 白名单归一化不会把非法条目算成可信（否则 admission 等于没做）。
 */
import test, { after } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";

import "./helpers/setup-globals.mjs";
import { client } from "../src/data/api.js";
import { createMockClient } from "./helpers/mock-client.mjs";
import { getLearningSpaceStatus } from "../src/data/learningSpaceApi.js";
import { isTrustedEmbedUrl, isSameOriginAsPage } from "../src/data/interactiveClassroom.js";

// setup-globals 里 location.href 为空串，pageOrigin() 需要一个合法页面地址才能
// 参与同源判定。这里固定成 Vite 开发端口，与真实使用一致。
globalThis.location = { pathname: "/learning-space", href: "http://127.0.0.1:5174/learning-space" };

const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true },
  appType: "custom",
  logLevel: "silent",
});

const { learningSpaceView } = await vite.ssrLoadModule("/src/pages/LearningSpacePage.jsx");

const APP_ORIGIN = "http://127.0.0.1:3000";

/** 一份"全都正常"的后端状态；各用例只覆盖自己关心的字段。 */
const readyStatus = (overrides = {}) => ({
  enabled: true,
  configured: true,
  available: true,
  unavailable: false,
  incompatible: false,
  compatibility: "compatible",
  degraded: false,
  capabilities: {},
  unavailable_capabilities: [],
  service: "openmaic",
  version: "1.0.3",
  embed_origin: APP_ORIGIN,
  browser_embed_available: true,
  browser_embed_reason: null,
  checked_at: "2026-09-20T00:00:00Z",
  reason: null,
  ...overrides,
});

after(async () => { await vite.close(); });

// ===== 适配器 =====

test("状态适配器 GET /openmaic/learning-space/status", async () => {
  const mock = createMockClient(client);
  try {
    mock.onGet("/openmaic/learning-space/status", readyStatus());
    const out = await getLearningSpaceStatus();
    assert.equal(mock.lastRequest().url, "/openmaic/learning-space/status");
    assert.equal(out.embed_origin, APP_ORIGIN);
  } finally {
    mock.reset();
    mock.clearTokens();
  }
});

// ===== 放行 =====

test("应用可达且公开 Origin 配置正确时放行内嵌", () => {
  const view = learningSpaceView(readyStatus());
  assert.equal(view.blocker, null);
  assert.equal(view.ready, true);
  assert.equal(view.origin, APP_ORIGIN);
  assert.deepEqual(view.origins, [APP_ORIGIN]);
});

test("降级（部分可选能力不可用）不影响内嵌", () => {
  const view = learningSpaceView(
    readyStatus({ degraded: true, unavailable_capabilities: ["tts"] }),
  );
  assert.equal(view.ready, true);
});

// ===== fail-closed =====

test("未配置公开 Origin 时不渲染内嵌", () => {
  const view = learningSpaceView(
    readyStatus({ embed_origin: null, browser_embed_available: false }),
  );
  assert.equal(view.ready, false);
  assert.equal(view.origin, null);
  assert.match(view.blocker.title, /浏览器访问尚未开放/);
});

test("后端尚未配置内部地址时给出「尚未启用」而非笼统报错", () => {
  const view = learningSpaceView(
    readyStatus({
      enabled: false,
      configured: false,
      available: false,
      embed_origin: null,
      reason: "学习空间未启用",
    }),
  );
  assert.equal(view.ready, false);
  assert.match(view.blocker.title, /尚未启用/);
});

test("应用进程没起来时指向独立的那个进程，而不是笼统说服务不可用", () => {
  const view = learningSpaceView(
    readyStatus({ enabled: false, available: false, unavailable: true, reason: null }),
  );
  assert.equal(view.ready, false);
  assert.match(view.blocker.title, /应用进程没有在运行/);
});

test("契约不兼容时重试无用，文案要说清", () => {
  const view = learningSpaceView(
    readyStatus({ enabled: false, available: false, compatibility: "incompatible" }),
  );
  assert.equal(view.ready, false);
  assert.match(view.blocker.title, /版本与后端约定不一致/);
});

test("公开 Origin 与本站同源时拒绝内嵌", () => {
  const view = learningSpaceView(
    readyStatus({ embed_origin: "http://127.0.0.1:5174" }),
  );
  assert.equal(isSameOriginAsPage("http://127.0.0.1:5174"), true, "前提：确实同源");
  assert.equal(view.ready, false);
  assert.match(view.blocker.title, /与本站同源/);
});

test("非法公开 Origin 归一化后为空，等同未配置", () => {
  for (const bad of ["", "   ", "not a url", "javascript:alert(1)", "file:///etc/passwd"]) {
    const view = learningSpaceView(readyStatus({ embed_origin: bad }));
    assert.deepEqual(view.origins, [], `不应把 ${JSON.stringify(bad)} 当作可信 Origin`);
    assert.equal(view.ready, false, `不应为 ${JSON.stringify(bad)} 放行`);
  }
});

test("缺少状态（尚未加载完 / 读取失败）不放行", () => {
  for (const value of [null, undefined]) {
    const view = learningSpaceView(value);
    assert.equal(view.ready, false);
    assert.equal(view.blocker, null, "无状态时不摆 blocker，交给加载 / 错误态");
  }
});

// ===== admission 与渲染点同源判定 =====

test("放行时该地址必然同时通过可信白名单与跨源判定", () => {
  const status = readyStatus();
  const view = learningSpaceView(status);
  assert.equal(view.ready, true);
  // ClassroomEmbed 的渲染条件是 safe = isTrustedEmbedUrl && !isSameOriginAsPage。
  // 两条都必须独立成立，否则页面会先放行、组件再拒绝，用户只看到一块空白色带。
  assert.equal(isTrustedEmbedUrl(view.origin, view.origins), true);
  assert.equal(isSameOriginAsPage(view.origin), false);
});

test("同源与非法 Origin 在组件层同样被拒 —— 纵深防御不会因为页面放行而失效", () => {
  for (const embedOrigin of [null, "http://127.0.0.1:5174", "ftp://127.0.0.1:3000"]) {
    const view = learningSpaceView(readyStatus({ embed_origin: embedOrigin }));
    const wouldRender = Boolean(view.origin)
      && isTrustedEmbedUrl(view.origin, view.origins)
      && !isSameOriginAsPage(view.origin);
    assert.equal(wouldRender, false, `组件层必须也拒绝: ${JSON.stringify(embedOrigin)}`);
  }
});
