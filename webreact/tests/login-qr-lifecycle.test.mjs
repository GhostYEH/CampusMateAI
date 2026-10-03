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
window.matchMedia ||= () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
globalThis.matchMedia = window.matchMedia;

const React = (await import("react")).default;
const appContext = React.createContext(null);
globalThis[Symbol.for("campusmate.app-context")] = appContext;
const apiModule = await import("../src/data/api.js");
const { createMockClient } = await import("./helpers/mock-client.mjs");
const mock = createMockClient(apiModule.client);
let releaseStatus;
let statusCalls = 0;
mock.onPost("/auth/qr/create", { session_id: "qr_lifecycle", browser_token: "browser_token", qr_payload: "campusmate://qr/test" });
mock.onGet("/auth/qr/qr_lifecycle/status", (config) => {
  statusCalls += 1;
  return new Promise((resolve) => {
    releaseStatus = () => resolve({ status: 200, data: { status: "scanned" }, config, headers: {} });
  });
});

const { createServer } = await import("vite");
const { fileURLToPath } = await import("node:url");
const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  plugins: [{
    name: "login-test-visual-stubs",
    enforce: "pre",
    resolveId(source, importer) {
      if (source === "qrcode") return "\0login-test-qrcode";
      if (importer?.endsWith("/LoginPage.jsx") && ["../components/RippleDistortion.jsx", "../components/LiquidChrome.jsx", "../components/TiltedCard.jsx", "../components/GlassSurface.jsx"].includes(source)) {
        return `\0login-test-${source.split("/").at(-1)}`;
      }
      return null;
    },
    load(id) {
      if (id === "\0login-test-qrcode") return "export default { toDataURL: async () => 'data:image/png;base64,test' };";
      if (!id.startsWith("\0login-test-")) return null;
      if (id.endsWith("RippleDistortion.jsx") || id.endsWith("LiquidChrome.jsx")) return "export default function VisualStub() { return null; }";
      return "export default function WrapperStub({ children }) { return children ?? null; }";
    },
  }],
  server: { middlewareMode: true, watch: null },
  ssr: { noExternal: ["qrcode"] },
  appType: "custom",
  logLevel: "silent",
});
after(async () => {
  releaseStatus?.();
  await Promise.race([vite.close(), new Promise((resolve) => setTimeout(resolve, 5000).unref?.())]);
});

const { createRoot } = await import("react-dom/client");
const { MemoryRouter } = await import("react-router-dom");
const { default: LoginPage } = await vite.ssrLoadModule("/src/pages/LoginPage.jsx");
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

test("QR status checks wait for the prior response and are invalidated on unmount", async () => {
  statusCalls = 0;
  releaseStatus = null;
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  const contextValue = {
    session: null,
    login: async () => {},
    applyQrLoginResult: () => {},
    tryTrustedLogin: async () => false,
    reduceMotion: true,
  };
  await React.act(async () => {
    root.render(React.createElement(appContext.Provider, { value: contextValue },
      React.createElement(MemoryRouter, null, React.createElement(LoginPage))));
  });
  for (let i = 0; i < 40 && !host.querySelector(".login-mode-switch"); i += 1) {
    await React.act(async () => { await wait(10); });
  }
  const qrButton = [...host.querySelectorAll("button")].find((button) => button.textContent.includes("扫码登录"));
  assert.ok(qrButton, "the login page must be mounted before starting QR polling");
  await React.act(async () => { qrButton.dispatchEvent(new window.Event("click", { bubbles: true })); await wait(20); });
  for (let i = 0; i < 130 && statusCalls === 0; i += 1) await wait(10);
  assert.equal(statusCalls, 1, `one QR status request should begin after the initial delay (requests: ${mock.requests.map((request) => `${request.method} ${request.url}`).join(", ")}; UI: ${host.textContent})`);

  await wait(1050);
  assert.equal(statusCalls, 1, "a slow status response must prevent overlapping QR requests");
  await React.act(async () => root.unmount());
  releaseStatus();
  await wait(1050);
  assert.equal(statusCalls, 1, "the in-flight response after unmount must not schedule another check");
  host.remove();
});
