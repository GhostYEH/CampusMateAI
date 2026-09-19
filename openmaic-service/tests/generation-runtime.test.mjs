import assert from "node:assert/strict";
import test from "node:test";

import { buildGeneratedStage } from "../src/generation/generator.ts";

test("simulation generation contains bounded experiment controls and formula", () => {
  const document = buildGeneratedStage("simulation", "牛顿第二定律");
  const content = document.scenes[0].content;
  assert.equal(content.type, "interactive");
  assert.equal(content.widgetType, "simulation");
  assert.equal(content.widgetConfig.formula, "force / mass");
  assert.ok(content.widgetConfig.parameters.some((parameter) => parameter.id === "force"));
  assert.ok(content.widgetConfig.parameters.some((parameter) => parameter.id === "mass"));
});

test("PBL generation contains executable phases and tasks", () => {
  const document = buildGeneratedStage("pbl", "设计一个校园节能方案");
  const phase = document.scenes[0].content.phases[0];
  assert.equal(document.scenes[0].content.type, "pbl");
  assert.ok(phase.id);
  assert.ok(phase.tasks?.[0]?.id);
});
