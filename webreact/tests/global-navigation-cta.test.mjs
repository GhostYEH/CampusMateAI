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

test("global navigation gives every route one shared liquid-glass surface", async () => {
  const [layoutStyles, navStyles] = await Promise.all([
    readFile(new URL("../src/styles/floating-layout.css", import.meta.url), "utf8"),
    readFile(new URL("../src/components/FloatingNav/FloatingNav.css", import.meta.url), "utf8"),
  ]);

  assert.match(layoutStyles, /\.floating-nav\s*\{[^}]*--floating-nav-foreground:\s*#17304f[^}]*background:\s*transparent/s);
  assert.match(navStyles, /color:\s*var\(--floating-nav-foreground,\s*#17304f\)/);
  assert.match(navStyles, /\.floating-nav-glass\s*\{[\s\S]*linear-gradient/);
  assert.match(navStyles, /\.floating-nav-list > li\.active \.floating-nav-button/);
  assert.doesNotMatch(layoutStyles, /data-(?:ogui-tone|contrast)/);
  assert.doesNotMatch(layoutStyles, /\.floating-nav:hover/);
  assert.doesNotMatch(layoutStyles, /transition:\s*width/);
  assert.match(layoutStyles, /\.floating-nav \.floating-nav-button\s*\{[^}]*gap:\s*5px[^}]*padding:\s*0 9px/s);
  assert.match(layoutStyles, /@media \(max-width: 1439px\)[\s\S]*\.floating-nav-label\s*\{[^}]*display:\s*none/s);
  assert.match(layoutStyles, /\.floating-nav-label\s*\{[^}]*max-width:\s*none[^}]*opacity:\s*1[^}]*transform:\s*none/s);
  assert.doesNotMatch(navStyles, /sylva-liquid|canvas/);
});

test("global navigation renders semantic route controls inside one glass surface", async () => {
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
  assert.equal((markup.match(/class="floating-nav-button"/g) || []).length, 10);
  assert.equal((markup.match(/class="[^"\s]*glass-surface[^"\s]*/g) || []).length > 0, true);
  assert.match(markup, /class="[^"]*floating-nav-glass/);
  assert.match(markup, /aria-current="page"/);
  assert.doesNotMatch(markup, /<canvas/);
  assert.doesNotMatch(markup, /sylva-liquid|data-static-controls/);
  assert.doesNotMatch(markup, /data-ogui-/);
  assert.doesNotMatch(markup, /data-contrast/);
});
