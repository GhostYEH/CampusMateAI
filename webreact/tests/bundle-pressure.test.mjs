import test from "node:test";
import assert from "node:assert/strict";
import { gzipSync } from "node:zlib";
import { fileURLToPath } from "node:url";
import { build } from "vite";

// Inspect the actual production dependency graph, including transitive imports.
const { output } = await build({
  root: fileURLToPath(new URL("..", import.meta.url)),
  logLevel: "silent",
  build: { write: false },
});
const chunks = new Map(output.filter((item) => item.type === "chunk").map((item) => [item.fileName, item]));
const entry = output.find((item) => item.type === "chunk" && item.isEntry);

function dependencies(root) {
  const visited = new Set();
  function visit(file) {
    if (visited.has(file)) return;
    visited.add(file);
    for (const child of chunks.get(file)?.imports || []) visit(child);
  }
  visit(root.fileName);
  return [...visited].map((file) => chunks.get(file)).filter(Boolean);
}

test("startup excludes login effects, route engines and classroom styles", () => {
  const startup = dependencies(entry);
  const modules = startup.flatMap((chunk) => Object.keys(chunk.modules));
  for (const fragment of ["node_modules/three/", "node_modules/@react-three/", "node_modules/ogl/", "node_modules/qrcode/", "node_modules/prosemirror-", "/pages/LoginPage.jsx", "/components/AppShell.jsx", "/styles/maic.css"]) {
    assert.ok(!modules.some((id) => id.includes(fragment)), `startup unexpectedly loads ${fragment}`);
  }
});

test("startup stays within the measured JavaScript and CSS budgets", () => {
  const startup = dependencies(entry);
  const gzipBytes = startup.reduce((total, chunk) => total + gzipSync(chunk.code).length, 0);
  const cssFiles = new Set(startup.flatMap((chunk) => [...chunk.viteMetadata.importedCss]));
  const cssBytes = [...cssFiles].reduce((total, file) => total + Buffer.byteLength(output.find((item) => item.fileName === file).source), 0);
  assert.ok(gzipBytes < 120_000, `startup JavaScript gzip: ${gzipBytes} bytes`);
  assert.ok(cssBytes < 220_000, `startup CSS: ${cssBytes} bytes`);
});

test("the homepage iframe wrapper does not fetch the separate 3D engine", () => {
  const home = output.find((item) => item.type === "chunk" && item.facadeModuleId?.endsWith("/pages/HomePage.jsx"));
  assert.ok(home, "homepage chunk exists");
  const modules = dependencies(home).flatMap((chunk) => Object.keys(chunk.modules));
  assert.ok(!modules.some((id) => id.includes("node_modules/three/") || id.includes("node_modules/@react-three/")));
});

test("the profile route no longer pulls the settings-only Three UI engine", () => {
  const profile = output.find((item) => item.type === "chunk" && item.facadeModuleId?.endsWith("/pages/ProfilePage.jsx"));
  assert.ok(profile, "profile chunk exists");
  const modules = dependencies(profile).flatMap((chunk) => Object.keys(chunk.modules));
  assert.ok(!modules.some((id) => id.includes("node_modules/three/") || id.includes("node_modules/@react-three/") || id.includes("node_modules/@designcodeio/threeui/")));
});

test("a direct classroom entry includes its progress and error styles", () => {
  const classroom = output.find((item) => item.type === "chunk" && item.facadeModuleId?.endsWith("/pages/magicclassClassroomEntryPage.jsx"));
  assert.ok(classroom, "classroom entry chunk exists");
  const cssFiles = new Set(dependencies(classroom).flatMap((chunk) => [...chunk.viteMetadata.importedCss]));
  const css = [...cssFiles].map((file) => output.find((item) => item.fileName === file).source).join("\n");
  assert.ok(css.includes(".magicclass-entry__progress"), "cold entry includes its progress layout");
  assert.ok(css.includes(".magicclass-entry__step"), "cold entry includes its generation steps");
});
