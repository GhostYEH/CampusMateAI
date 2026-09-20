import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const contextSource = await readFile(new URL("../src/app/AppContext.jsx", import.meta.url), "utf8");
const appSource = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
const typingSource = await readFile(new URL("../src/components/TypingPlaceholderLayer.jsx", import.meta.url), "utf8");

test("AppContext keeps one global identity across Fast Refresh module instances", () => {
  assert.match(contextSource, /Symbol\.for\("campusmate\.app-context"\)/);
  assert.match(contextSource, /globalThis\[APP_CONTEXT_KEY\] \|\| createContext\(null\)/);
  assert.match(contextSource, /globalThis\[APP_CONTEXT_KEY\] = AppContext/);
});

test("provider and global consumers use the same AppContext module contract", () => {
  assert.match(appSource, /import \{ AppProvider, useApp \} from "\.\/app\/AppContext\.jsx"/);
  assert.match(appSource, /<AppProvider>/);
  assert.match(typingSource, /import \{ useApp \} from "\.\.\/app\/AppContext\.jsx"/);
  assert.match(typingSource, /useApp\(\)/);
});
