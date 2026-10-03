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
globalThis.MutationObserver = window.MutationObserver;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const { createServer } = await import("vite");
const { fileURLToPath } = await import("node:url");
const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true, watch: null },
  appType: "custom",
  logLevel: "silent",
});
after(async () => {
  await Promise.race([vite.close(), new Promise((resolve) => setTimeout(resolve, 5000).unref?.())]);
});

const React = (await import("react")).default;
const { createRoot } = await import("react-dom/client");
const { default: DigitalHumanPanel } = await vite.ssrLoadModule("/src/components/DigitalHumanPanel.jsx");

function dispatchMessage(source, origin, type) {
  const event = new window.Event("message");
  Object.defineProperties(event, {
    source: { value: source },
    origin: { value: origin },
    data: { value: { source: "campusmate-unity", type } },
  });
  window.dispatchEvent(event);
}

test("digital human stays static until woken, accepts only its iframe, and retries without remounting on ready", async () => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  const frameWindow = {};
  let readyCount = 0;
  function Harness() {
    const [status, setStatus] = React.useState("loading");
    return React.createElement(DigitalHumanPanel, {
      speaking: false,
      muted: false,
      status,
      canReplay: true,
      onReady: () => { readyCount += 1; setStatus("ready"); },
      onError: () => setStatus("error"),
      onToggleMuted: () => {},
      onStop: () => {},
      onReplay: () => {},
    });
  }
  await React.act(async () => root.render(React.createElement(Harness)));
  assert.equal(host.querySelector("iframe"), null, "mount must leave the Unity iframe unloaded");
  assert.match(host.textContent, /点击唤醒/);

  const wake = host.querySelector(".digital-human-wake");
  await React.act(async () => { wake.dispatchEvent(new window.Event("click", { bubbles: true })); });
  let frame = host.querySelector("iframe");
  assert.ok(frame, "the explicit wake action should mount the iframe");
  Object.defineProperty(frame, "contentWindow", { value: frameWindow, configurable: true });
  await React.act(async () => { dispatchMessage({}, window.location.origin, "ready"); });
  assert.equal(readyCount, 0, "same-origin messages from another window must be ignored");
  await React.act(async () => { dispatchMessage(frameWindow, "https://attacker.example", "ready"); });
  assert.equal(readyCount, 0, "messages from another origin must be ignored");

  await React.act(async () => { dispatchMessage(frameWindow, window.location.origin, "error"); });
  assert.ok(host.querySelector(".digital-human-retry"), "a load error must retain a retry action");
  const retry = host.querySelector(".digital-human-retry");
  await React.act(async () => { retry.dispatchEvent(new window.Event("click", { bubbles: true })); });
  frame = host.querySelector("iframe");
  Object.defineProperty(frame, "contentWindow", { value: frameWindow, configurable: true });
  await React.act(async () => { dispatchMessage(frameWindow, window.location.origin, "ready"); });
  assert.equal(readyCount, 1, "the iframe's ready message should be accepted");
  assert.equal(host.querySelector("iframe"), frame, "handling ready must not remount the Unity iframe");

  await React.act(async () => { dispatchMessage(frameWindow, window.location.origin, "error"); });
  assert.ok(host.querySelector(".digital-human-retry"), "a Unity error after retry must return to the fallback and allow another retry");
  await React.act(async () => root.unmount());
  host.remove();
});
