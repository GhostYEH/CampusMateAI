import assert from "node:assert/strict";
import { after, test } from "node:test";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true },
  appType: "custom",
  logLevel: "silent",
});

after(async () => {
  await vite.close();
});

test("liquid metal keeps its base plate without allocating WebGL until interaction", async () => {
  const { default: LiquidMetalButton } = await vite.ssrLoadModule(
    "/src/components/LiquidMetalButton.jsx",
  );

  const markup = renderToStaticMarkup(
    createElement(LiquidMetalButton, {
      className: "sylva-card-link",
      children: "全部待办",
      "aria-label": "查看全部待办",
    }),
  );

  assert.match(markup, /^<span class="sylva-liquid-stage/);
  assert.match(markup, /class="sylva-liquid-plate" aria-hidden="true"/);
  assert.doesNotMatch(markup, /class="sylva-liquid-fx"/);
  assert.match(markup, /<button[^>]*class="sylva-liquid-control sylva-card-link"/);
  assert.match(markup, />全部待办<\/button><\/span>$/);
});

test("navigation buttons leave canvas ownership to the shared client renderer", async () => {
  const { default: LiquidMetalButton } = await vite.ssrLoadModule(
    "/src/components/LiquidMetalButton.jsx",
  );

  const markup = renderToStaticMarkup(
    createElement(LiquidMetalButton, {
      variant: "nav",
      active: true,
      defer: true,
      useSharedNavigationRenderer: true,
      className: "floating-nav-button",
      "aria-label": "首页",
      "aria-current": "page",
      children: "首页",
    }),
  );

  assert.match(markup, /sylva-liquid-stage--nav/);
  assert.match(markup, /data-active="true"/);
  assert.doesNotMatch(markup, /class="sylva-liquid-fx"/);
  assert.match(markup, /aria-current="page"/);
  assert.match(markup, /<button[^>]*class="sylva-liquid-control floating-nav-button"/);
});

test("liquid metal button in defer mode without active mounts lazily", async () => {
  const { default: LiquidMetalButton } = await vite.ssrLoadModule(
    "/src/components/LiquidMetalButton.jsx",
  );

  const markup = renderToStaticMarkup(
    createElement(LiquidMetalButton, {
      variant: "nav",
      active: false,
      defer: true,
      className: "floating-nav-button",
      "aria-label": "我的课程",
      children: "我的课程",
    }),
  );

  assert.match(markup, /sylva-liquid-stage--nav/);
  assert.match(markup, /class="sylva-liquid-plate" aria-hidden="true"/);
  assert.doesNotMatch(markup, /class="sylva-liquid-fx"/);
  assert.doesNotMatch(markup, /data-active="true"/);
});

test("liquid metal button does not allocate WebGL when effects are disabled", async () => {
  const { default: LiquidMetalButton } = await vite.ssrLoadModule(
    "/src/components/LiquidMetalButton.jsx",
  );

  const markup = renderToStaticMarkup(
    createElement(LiquidMetalButton, {
      variant: "nav",
      active: true,
      disableEffects: true,
      className: "floating-nav-button",
      "aria-label": "首页",
      children: "首页",
    }),
  );

  assert.match(markup, /class="sylva-liquid-plate" aria-hidden="true"/);
  assert.doesNotMatch(markup, /class="sylva-liquid-fx"/);
});

test("liquid metal surface preserves nested controls while deferring its canvas", async () => {
  const { default: LiquidMetalSurface } = await vite.ssrLoadModule(
    "/src/components/LiquidMetalSurface.jsx",
  );

  const markup = renderToStaticMarkup(
    createElement(LiquidMetalSurface, {
      className: "topbar-search-surface",
      "aria-label": "全局搜索",
      children: createElement("input", { name: "global-search" }),
    }),
  );

  assert.match(markup, /sylva-liquid-stage--surface/);
  assert.match(markup, /class="sylva-liquid-plate" aria-hidden="true"/);
  assert.match(markup, /name="global-search"/);
  assert.doesNotMatch(markup, /class="sylva-liquid-fx"/);
});

test("liquid metal runtime explicitly releases a disposed WebGL context", async () => {
  const { LIQUID_METAL_MAX_FPS, releaseWebGLContext } = await vite.ssrLoadModule(
    "/src/components/liquidMetalScene.js",
  );
  let released = 0;
  const extension = { loseContext: () => { released += 1; } };
  const gl = {
    getExtension(name) {
      return name === "WEBGL_lose_context" ? extension : null;
    },
  };

  releaseWebGLContext(gl);

  assert.equal(released, 1);
  assert.equal(LIQUID_METAL_MAX_FPS, 30);
});

test("liquid metal runtime keeps default 30 FPS and DPR 2 budgets", async () => {
  const { LIQUID_METAL_MAX_FPS, LIQUID_METAL_DPR_CAP } = await vite.ssrLoadModule(
    "/src/components/liquidMetalScene.js",
  );

  assert.equal(LIQUID_METAL_MAX_FPS, 30);
  assert.equal(LIQUID_METAL_DPR_CAP, 2);
});

test("liquid metal runtime supports navigation quality overrides", async () => {
  const { readFileSync } = await import("node:fs");
  const runtime = readFileSync(new URL("../src/components/liquidMetalScene.js", import.meta.url), "utf8");
  assert.match(runtime, /maxFps/);
  assert.match(runtime, /dprCap/);
  assert.match(runtime, /LIQUID_METAL_DPR_CAP/);
});

test("liquid metal runtime falls back for invalid quality parameters", async () => {
  const { readFileSync } = await import("node:fs");
  const runtime = readFileSync(new URL("../src/components/liquidMetalScene.js", import.meta.url), "utf8");
  assert.match(runtime, /Number\.isFinite/);
  assert.match(runtime, /maxFps/);
  assert.match(runtime, /dprCap/);
});

test("liquid metal runtime pauses frames while the page is hidden", async () => {
  const { readFileSync } = await import("node:fs");
  const runtime = readFileSync(new URL("../src/components/liquidMetalScene.js", import.meta.url), "utf8");
  assert.match(runtime, /visibilitychange/);
  assert.match(runtime, /document\.hidden|document\.visibilityState/);
});

test("liquid metal runtime removes its visibility listener on cleanup", async () => {
  const { readFileSync } = await import("node:fs");
  const runtime = readFileSync(new URL("../src/components/liquidMetalScene.js", import.meta.url), "utf8");
  assert.match(runtime, /visibilitychange/);
  assert.match(runtime, /removeEventListener/);
});

test("navigation liquid renderer exposes one reusable target lifecycle", async () => {
  const runtime = await vite.ssrLoadModule("/src/components/liquidMetalScene.js");

  assert.equal(typeof runtime.getSharedNavigationLiquidRenderer, "function");
});

test("navigation hover gate ignores layout-only pointer boundary changes", async () => {
  const { createStableHoverGate } = await vite.ssrLoadModule(
    "/src/components/FloatingNav/LiquidMetalNav.jsx",
  );
  const gate = createStableHoverGate();

  gate.notePointerMove();
  assert.equal(gate.claim(1), true);
  assert.equal(gate.release(1), false);
  assert.equal(gate.claim(2), false);

  gate.notePointerMove();
  assert.equal(gate.release(1), true);
  assert.equal(gate.claim(2), true);
  assert.equal(gate.release(2, { force: true }), true);
});
