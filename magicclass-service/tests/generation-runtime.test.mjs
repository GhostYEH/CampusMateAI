import assert from "node:assert/strict";
import test from "node:test";

import { readFile } from "node:fs/promises";
import { Script } from "node:vm";
import { buildGeneratedStage, materializeGeneratedStage, reviewGeneratedStage } from "../src/generation/generator.ts";
import { PARAMETER_EXPERIMENT_PROFILE } from "../src/generation/parameter-experiment.ts";

test("simulation generation contains bounded experiment controls and formula", () => {
  const document = buildGeneratedStage("simulation", "牛顿第二定律");
  const content = document.scenes[0].content;
  assert.equal(content.type, "interactive");
  assert.equal(content.widgetType, "simulation");
  assert.equal(content.widgetConfig.formula, "force / mass");
  assert.equal(content.widgetConfig.nativeRenderer, PARAMETER_EXPERIMENT_PROFILE);
  assert.match(content.html, /id="widget-config"/);
  assert.ok(content.widgetConfig.parameters.some((parameter) => parameter.id === "force"));
  assert.ok(content.widgetConfig.parameters.some((parameter) => parameter.id === "mass"));
});

test("adopts generated arithmetic data and supplies sandbox controls in the managed classroom", () => {
  const lab = {
    type: "simulation",
    nativeRenderer: PARAMETER_EXPERIMENT_PROFILE,
    description: "观察电压的影响",
    controls: [{ id: "voltage", label: "电压", unit: "V", min: 0, max: 12, step: 1, value: 6 }],
    resultLabel: "电流",
    resultUnit: "A",
    expression: ["voltage", 3, "/"],
    chartParameter: "voltage",
  };
  const make = (widgetConfig) => ({
    stage: { name: "数值实验" },
    scenes: [{ title: "用电实验", type: "interactive", content: {
      type: "interactive", widgetType: "simulation", widgetConfig, html: "<p>观察电流</p>",
    } }],
  });
  assert.deepEqual(reviewGeneratedStage(make(lab), "simulation", "观察电流"), []);
  assert.match(reviewGeneratedStage(make({ ...lab, expression: ["voltage", "/"] }), "simulation", "观察电流")[0], /参数实验配置无效/);
  const document = materializeGeneratedStage(make(lab), { mode: "simulation" });
  const content = document.scenes[0].content;
  assert.equal(content.widgetConfig.nativeRenderer, PARAMETER_EXPERIMENT_PROFILE);
  assert.deepEqual(content.widgetConfig.expression, lab.expression);
  assert.equal(content.widgetConfig.formula, undefined);
  assert.match(content.html, /<input|createElement\(['"]input['"]\)/);
  const script = content.html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
  assert.ok(script);
  assert.doesNotThrow(() => new Script(script));
});

test("a spatial experiment satisfies a simulation request without adding an unrelated force template", () => {
  const document = materializeGeneratedStage({
    stage: { name: "观察空间形状" },
    scenes: [{ title: "几何模型", type: "interactive", content: {
      type: "interactive", widgetType: "visualization3d", html: "<p>模型</p>",
    } }],
  }, { mode: "simulation" });
  assert.deepEqual(document.scenes.map((scene) => scene.content.widgetType), ["visualization3d"]);
});

test("the two classroom generators ship the same parameter contract and browser runtime", async () => {
  const managed = new URL("../src/generation/parameter-experiment.ts", import.meta.url);
  const classic = new URL("../../magicclass-app/packages/@magicclass/generation/src/parameter-experiment.ts", import.meta.url);
  const source = await readFile(managed, "utf8");
  assert.equal(source.replace(/\r\n/g, "\n"), (await readFile(classic, "utf8")).replace(/\r\n/g, "\n"));
});

test("PBL generation produces a runnable project, not an unreadable phase list", () => {
  // 目标形状由**渲染器**决定：它只认 `content.projectV2`（或历史 projectConfig）。
  // 此前这里产出的是 `{ phases: [...] }`，两者都不是，于是每个 PBL 场景在课堂里
  // 都是一个"项目尚未生成"的占位面板。所以这条测试断言的不是"有没有阶段"，而是
  // **渲染器的可运行判定能不能过**——判定规则同步自
  // `webreact/src/magicclass/scene/lib/pbl-types-guards.js` 的 `isRunnablePBLProjectV2`。
  const document = buildGeneratedStage("pbl", "设计一个校园节能方案");
  const content = document.scenes[0].content;
  assert.equal(content.type, "pbl");
  assert.equal(content.phases, undefined, "旧形态不应再出现，它会渲染成占位面板");

  const project = content.projectV2;
  assert.ok(project, "必须产出 projectV2，否则渲染器退回占位");
  for (const key of ["milestones", "roles", "submissions", "evaluations", "threads", "engagementEvents"]) {
    assert.ok(Array.isArray(project[key]), `${key} 必须是数组`);
  }
  assert.ok(
    project.roles.some((role) => role.type === "instructor" && String(role.id ?? "").trim() && typeof role.name === "string"),
    "至少要有一个 id 非空的 instructor 角色——工作台的指导老师线索靠它绑定",
  );
  assert.ok(project.milestones.length > 0, "至少要有一个阶段");
  for (const milestone of project.milestones) {
    assert.ok(milestone.microtasks.length > 0, "每个阶段至少一个任务");
    for (const microtask of milestone.microtasks) {
      assert.ok(String(microtask.id ?? "").trim(), "任务必须有非空 id");
      assert.equal(typeof microtask.title, "string", "任务必须有标题");
    }
  }
  assert.ok(project.threads.every((thread) => Array.isArray(thread.messages)), "线索必须带 messages 数组");
});

test("PBL composition is deterministic so read-time projection stays idempotent", () => {
  // 读时投影靠"内容没变就不重写"来保证不触碰存量字节。合成里一旦出现时间戳或
  // 随机量，这条判断就会永久失效。
  const first = buildGeneratedStage("pbl", "设计一个校园节能方案").scenes[0].content;
  const second = buildGeneratedStage("pbl", "设计一个校园节能方案").scenes[0].content;
  assert.deepEqual(first, second);
});

