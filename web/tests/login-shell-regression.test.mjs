import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createServer } from "vite";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
let vite;

before(async () => {
  vite = await createServer({
    root: webRoot,
    appType: "custom",
    logLevel: "silent",
    server: { middlewareMode: true },
  });
});

after(async () => {
  await vite?.close();
});

test("registers the existing student home view at /home", async () => {
  const originalWindow = globalThis.window;
  const originalLocation = globalThis.location;
  const originalDocument = globalThis.document;
  globalThis.window = {
    history: { state: null, length: 1, replaceState() {}, pushState() {}, go() {} },
    location: { protocol: "http:", host: "localhost", pathname: "/", search: "", hash: "", href: "http://localhost/", assign() {}, replace() {} },
    addEventListener() {},
    removeEventListener() {},
  };
  globalThis.location = globalThis.window.location;
  globalThis.document = { addEventListener() {}, removeEventListener() {}, querySelector() { return null; }, visibilityState: "visible" };

  try {
    const { default: router } = await vite.ssrLoadModule("/src/router.js");
    const homeRoute = router.resolve("/home").matched.at(-1);
    const loadHomeView = homeRoute.components.default;
    assert.equal(typeof loadHomeView, "function");
    const homeViewModule = await loadHomeView();
    assert.equal(homeViewModule.default.__name, "StudentHomeView");
  } finally {
    globalThis.window = originalWindow;
    globalThis.location = originalLocation;
    globalThis.document = originalDocument;
  }
});

test("uses the public login video and no deleted campus-night image", async () => {
  const [loginView, styles] = await Promise.all([
    readFile(path.join(webRoot, "src", "views", "LoginView.vue"), "utf8"),
    readFile(path.join(webRoot, "src", "styles.css"), "utf8"),
  ]);

  assert.match(loginView, /<video\s+[^>]*src="\/assets\/login-campus\.mp4"/);
  assert.doesNotMatch(styles, /campus-night\.jpg/);
});
