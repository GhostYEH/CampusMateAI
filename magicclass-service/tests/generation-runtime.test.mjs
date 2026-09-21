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

test("PBL generation produces a runnable project, not an unreadable phase list", () => {
  // 目标形状由**渲染器**决定：它只认 `content.projectV2`（或历史 projectConfig）。
  // 此前这里产出的是 `{ phases: [...] }`，两者都不是，于是每个 PBL 场景在课堂里
  // 都是一个"项目尚未生成"的占位面板。所以这条测试断言的不是"有没有阶段"，而是
  // **渲染器的可运行判定能不能过**——判定规则同步自
  // `webreact/src/maic/scene/lib/pbl-types-guards.js` 的 `isRunnablePBLProjectV2`。
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

