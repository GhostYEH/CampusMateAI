import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const styles = await readFile(new URL("../src/styles/floating-layout.css", import.meta.url), "utf8");
const shell = await readFile(new URL("../src/components/AppShell.jsx", import.meta.url), "utf8");

test("shared shell exposes a navigation clearance token for every route", () => {
  assert.match(styles, /--floating-nav-clearance:/);
  assert.match(styles, /\.route-stage[^}]*padding-top:\s*var\(--floating-nav-clearance\)/s);
  assert.match(shell, /className="route-stage"/);
});

test("route stage reserves room for the bottom mobile dock", () => {
  assert.match(styles, /\.route-stage[^}]*padding-bottom:[^}]*--floating-nav-bottom-clearance/s);
  assert.match(styles, /--floating-nav-bottom-clearance:/);
});
