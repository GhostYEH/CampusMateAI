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

test("liquid metal keeps the authored stage, plate, canvas, and native button layers", async () => {
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
  assert.match(markup, /class="sylva-liquid-fx" aria-hidden="true"/);
  assert.match(markup, /<button[^>]*class="sylva-liquid-control sylva-card-link"/);
  assert.match(markup, />全部待办<\/button><\/span>$/);
});
