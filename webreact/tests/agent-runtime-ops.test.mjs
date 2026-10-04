import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

test("the application exposes no administrator operations page or preload", () => {
  const root = new URL("../src/", import.meta.url);
  for (const file of ["App.jsx", "app/routePreload.js"]) {
    const source = fs.readFileSync(new URL(file, root), "utf8");
    assert.doesNotMatch(source, /AgentRuntimeOpsPage|\/admin\//);
  }
  assert.equal(fs.existsSync(new URL("data/agentObservabilityApi.js", root)), false);
});
