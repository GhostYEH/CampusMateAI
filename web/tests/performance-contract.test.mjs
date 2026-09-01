import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const routerSource = await readFile(new URL("../src/router.js", import.meta.url), "utf8");
const viteSource = await readFile(new URL("../vite.config.mjs", import.meta.url), "utf8");

test("route views outside the initial shells are lazy loaded", () => {
  const eagerViewImports = [...routerSource.matchAll(/^import\s+\w+\s+from\s+"(\.\/views\/[^"]+)";/gm)]
    .map((match) => match[1]);

  assert.deepEqual(eagerViewImports, [
    "./views/LoginView.vue",
    "./views/AppShell.vue",
  ]);
  assert.match(routerSource, /import\("\.\/views\/student\/StudentHomeView\.vue"\)/);
});

test("production build creates stable vendor cache groups", () => {
  assert.match(viteSource, /manualChunks/);
  assert.match(viteSource, /vue-vendor/);
  assert.match(viteSource, /qr-tools/);
  assert.match(viteSource, /markdown-tools/);
});
