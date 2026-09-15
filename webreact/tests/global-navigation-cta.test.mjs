import assert from "node:assert/strict";
import { after, test } from "node:test";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { createServer } from "vite";

const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true },
  appType: "custom",
  logLevel: "silent",
});

after(async () => {
  await vite.close();
});

test("global navigation gives every route the homepage primary-action plate", async () => {
  const [buttonEffects, layoutStyles, navStyles] = await Promise.all([
    readFile(new URL("../src/styles/button-effects.css", import.meta.url), "utf8"),
    readFile(new URL("../src/styles/floating-layout.css", import.meta.url), "utf8"),
    readFile(new URL("../src/components/FloatingNav/LiquidMetalNav.css", import.meta.url), "utf8"),
  ]);

  assert.match(layoutStyles, /\.floating-nav\s*\{[^}]*--floating-nav-foreground:\s*#f7f8f2[^}]*background:\s*transparent/s);
  assert.match(navStyles, /color:\s*var\(--floating-nav-foreground,\s*#f7f8f2\)/);
  assert.doesNotMatch(buttonEffects, /\.sylva-liquid-stage--nav \.sylva-liquid-plate\s*\{[^}]*opacity:\s*0/s);
  assert.doesNotMatch(buttonEffects, /--floating-nav-effect-(?:size|x)/);
  assert.doesNotMatch(layoutStyles, /data-(?:ogui-tone|contrast)/);
  assert.doesNotMatch(layoutStyles, /\.floating-nav:hover/);
  assert.doesNotMatch(layoutStyles, /transition:\s*width/);
  assert.match(layoutStyles, /\.floating-nav-label\s*\{[^}]*max-width:\s*none[^}]*opacity:\s*1[^}]*transform:\s*none/s);
  assert.match(layoutStyles, /\.floating-nav \.sylva-liquid-stage--nav:hover[^}]*translate:\s*none/s);
});

test("global navigation renders every route as a standalone primary liquid-metal control", async () => {
  const { default: FloatingNav } = await vite.ssrLoadModule(
    "/src/components/FloatingNav/FloatingNav.jsx",
  );

  const originalConsoleError = console.error;
  let markup;
  try {
    console.error = () => {};
    markup = renderToStaticMarkup(
      createElement(
        MemoryRouter,
        { initialEntries: ["/home"] },
        createElement(FloatingNav),
      ),
    );
  } finally {
    console.error = originalConsoleError;
  }

  assert.match(markup, /^<div class="floating-nav floating-nav--primary"/);
  assert.equal((markup.match(/sylva-liquid-stage--nav/g) || []).length, 9);
  assert.equal((markup.match(/class="sylva-liquid-plate"/g) || []).length, 9);
  assert.match(markup, /data-static-controls="true"/);
  assert.doesNotMatch(markup, /<canvas/);
  assert.doesNotMatch(markup, /data-ogui-/);
  assert.doesNotMatch(markup, /data-contrast/);
});
