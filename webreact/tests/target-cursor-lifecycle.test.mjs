import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const targetCursor = readFileSync(new URL("../src/components/TargetCursor.jsx", import.meta.url), "utf8");

test("target cursor clears the highlighted target when editing removes it", () => {
  assert.match(targetCursor, /MutationObserver/);
  assert.match(targetCursor, /activeTarget\.isConnected/);
});
