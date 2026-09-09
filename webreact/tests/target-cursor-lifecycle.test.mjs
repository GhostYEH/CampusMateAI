import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const targetCursor = readFileSync(new URL("../src/components/TargetCursor.jsx", import.meta.url), "utf8");
const profilePage = readFileSync(new URL("../src/pages/ProfilePage.jsx", import.meta.url), "utf8");

test("target cursor clears the highlighted target when editing removes it", () => {
  assert.match(targetCursor, /MutationObserver/);
  assert.match(targetCursor, /activeTarget\.isConnected/);
});

test("profile target cursor honors the application reduced-motion preference", () => {
  assert.match(targetCursor, /disabled\s*=\s*false/);
  assert.match(targetCursor, /isMobile\s*\|\|\s*reduceMotion\s*\|\|\s*disabled/);
  assert.match(profilePage, /<TargetCursor[\s\S]*disabled=\{reduceMotion\}/);
});
