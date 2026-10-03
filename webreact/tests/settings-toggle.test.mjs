import test, { after } from "node:test";
import assert from "node:assert/strict";
import "./helpers/setup-globals.mjs";
import { parseHTML } from "linkedom";

const { window, document } = parseHTML("<!doctype html><html><body></body></html>");
globalThis.window = window;
globalThis.document = document;
Object.defineProperty(globalThis, "navigator", { value: window.navigator, configurable: true, writable: true });
globalThis.HTMLElement = window.HTMLElement;
globalThis.Element = window.Element;
globalThis.Node = window.Node;
globalThis.Event = window.Event;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const { createServer } = await import("vite");
const { fileURLToPath } = await import("node:url");
const vite = await createServer({ root: fileURLToPath(new URL("..", import.meta.url)), server: { middlewareMode: true, watch: null }, appType: "custom", logLevel: "silent" });
after(async () => { await Promise.race([vite.close(), new Promise((resolve) => setTimeout(resolve, 5000).unref?.())]); });

const React = (await import("react")).default;
const { createRoot } = await import("react-dom/client");
const { default: SkeuomorphicGlassToggle } = await vite.ssrLoadModule("/src/components/settings/SkeuomorphicGlassToggle.jsx");

test("the settings switch is a controlled native button with accessible state", async () => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  function Harness() {
    const [value, setValue] = React.useState(false);
    return React.createElement(SkeuomorphicGlassToggle, { label: "减少动态效果", value, onChange: setValue });
  }
  await React.act(async () => root.render(React.createElement(Harness)));
  const toggle = host.querySelector('button[role="switch"]');
  assert.ok(toggle);
  assert.equal(toggle.type, "button");
  assert.equal(toggle.getAttribute("aria-checked"), "false");
  assert.equal(toggle.getAttribute("aria-label"), "减少动态效果");
  assert.equal(toggle.getAttribute("tabindex"), "0", "switch must remain in the keyboard tab order");
  assert.equal(toggle.tagName, "BUTTON", "native button semantics provide Enter/Space activation");
  await React.act(async () => { toggle.dispatchEvent(new window.Event("click", { bubbles: true })); });
  assert.equal(host.querySelector('button[role="switch"]').getAttribute("aria-checked"), "true");
  assert.equal(host.querySelectorAll("button").length, 1, "the setting wrapper must not add a nested interactive control");
  await React.act(async () => root.unmount());
  host.remove();
});
