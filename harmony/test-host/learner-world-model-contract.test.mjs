/**
 * 鸿蒙端世界模型消费的 host 契约测试（纯 Node，不需要 DevEco / 设备）。
 *
 * 为什么存在：鸿蒙的运行时单测（hypium）需要 DevEco Studio + HarmonyOS SDK，
 * 在只有 Node 的环境里跑不了。这里用源码级契约把**不可退让的展示规则**钉住，
 * 让"页面把候选模型当成了确定性结果""模拟区留了个空按钮""用 delta 猜重规划"
 * 这类退化在 CI 上就能被拦住，而不是等到设备上人工发现。
 *
 * 运行：node --test harmony/test-host/*.test.mjs
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ETS = join(HERE, "..", "entry", "src", "main", "ets");
const read = (relative) => readFileSync(join(ETS, relative), "utf8");

const models = read(join("data", "AgentRuntimeModels.ets"));
const repository = read(join("repository", "AgentRuntimeRepository.ets"));
const page = read(join("features", "goals", "GoalExecutionPage.ets"));
const testList = readFileSync(
  join(HERE, "..", "entry", "src", "test", "List.test.ets"), "utf8",
);

test("repository calls the real learner-state endpoints", () => {
  for (const path of [
    "learner-state/snapshots?projection_kind=",
    "learner-state/forecasts?page=1",
    "learner-state/data-controls",
    "learner-state/model-transparency",
    "adaptive-interventions?page=1",
    "/outcome`",
  ]) {
    assert.ok(repository.includes(path), `仓库层必须调用 ${path}`);
  }
  assert.match(repository, /learner-state\/data-controls\/\$\{encodeURIComponent\(sourceKey\)\}/);
});

test("repository never exposes a client-side path that creates or replaces plans", () => {
  // 干预记录与自动重规划只能由后端后台闭环产生；客户端只允许 GET 干预资源。
  const lines = repository.split("\n");
  lines.forEach((line, index) => {
    if (!line.includes("adaptive-interventions")) return;
    assert.ok(
      !/http\.RequestMethod\.(POST|PUT|PATCH|DELETE)/.test(line),
      `第 ${index + 1} 行：干预资源不得有客户端写入入口`,
    );
  });
  for (const forbidden of ["/replan-intervention", "replan_decision", "link_superseded"]) {
    assert.ok(!repository.includes(forbidden), `不得存在客户端干预写入入口：${forbidden}`);
  }
});

test("models parse the fields the page renders, including degradation markers", () => {
  for (const marker of [
    "candidate_annotation",
    "static candidateAnnotation(",
    "static learnerStateSnapshotPage(",
    "static forecastSummary(",
    "static dataSourceControl(",
    "static modelTransparency(",
    "static adaptiveInterventionOutcome(",
  ]) {
    assert.ok(models.includes(marker), `模型层必须提供 ${marker}`);
  }
  for (const field of ["data_quality", "warning_codes", "limitations", "read_only", "affects_production"]) {
    assert.ok(models.includes(field), `降级/只读标记不得省略：${field}`);
  }
});

test("candidate annotation is identifiable, degradable and never shown as production", () => {
  assert.match(page, /候选模型建议（只读）/);
  assert.match(page, /已回退到确定性结果：/);
  assert.match(page, /这是候选模型的只读展示，不会修改你的状态、计划或待办。/);
  for (const reason of [
    "canary_feature_flag_disabled",
    "candidate_model_not_configured",
    "model_shadow_paused_for_user",
    "no_promotion_decision",
    "quality_gates_failed",
    "circuit_breaker_open",
    "MODEL_RATE_LIMITED",
    "MODEL_TIMEOUT",
    "MODEL_SCHEMA_INVALID",
    "MODEL_POLICY_VIOLATION",
  ]) {
    assert.ok(page.includes(reason), `降级原因 ${reason} 必须有中文文案`);
  }
});

test("auto-replan is only announced when the backend persisted APPLIED", () => {
  assert.match(page, /decision_status === 'APPLIED'/);
  assert.match(page, /已调整学习计划/);
  // 不允许按差值自行推测系统决定。
  assert.ok(!/delta\s*[<>]/.test(page), "不得按 delta 猜测重规划结果");
  assert.ok(!page.includes("decision_reason_codes.length > 0 ? '已调整"), "必须以后端状态为准");
});

test("intervention scope is stated explicitly and never implies the loop is skipped", () => {
  assert.ok(models.includes("scope_type"), "模型层必须解析 scope_type");
  assert.match(page, /this\.interventionOutcome\.scope_type === 'PLAN'/);
  // 关键：无目标计划同样观测、同样会安全替换计划 —— 不得写成"仅观测/不参与"。
  assert.match(page, /系统按计划范围观测与评估，有证据时同样会安全替换计划。/);
  assert.ok(!/仅观测|不参与自动重规划|不会调整计划/.test(page), "不得暗示无目标计划被排除在闭环外");
});

test("every world-model area required by the mobile parity checklist is present", () => {
  for (const heading of [
    "学生世界模型（只读）",
    "状态摘要",
    "风险预测",
    "计划与自动重规划",
    "反事实模拟",
    "数据源控制",
    "模型透明度",
  ]) {
    assert.ok(page.includes(heading), `世界模型区域缺少：${heading}`);
  }
});

test("counterfactual simulation degrades explicitly instead of rendering an empty control", () => {
  assert.match(page, /本端暂未提供反事实模拟入口；模拟是纯只读推演，不会执行干预。/);
  assert.ok(!page.includes("运行模拟"), "未实现的模拟能力不得渲染可点击按钮");
});

test("world-model failure only degrades its own card, not the whole page", () => {
  assert.match(page, /@State worldModelDegraded: string = ''/);
  assert.match(page, /只读降级：/);
  // 降级状态必须与页级 error 分开，否则一次失败会连目标/计划一起消失。
  const reloadBlock = page.slice(page.indexOf("async reloadWorldModel"), page.indexOf("async toggleDataSource"));
  assert.ok(!reloadBlock.includes("this.error ="), "世界模型加载失败不得写页级 error");
});

test("data source controls stay read-only for learner state", () => {
  assert.match(page, /async toggleDataSource\(sourceKey: string, status: string\)/);
  assert.match(page, /setDataSourceStatus\(sourceKey, status\)/);
  // 只允许切换 ENABLED / PAUSED 两种状态。
  const toggle = page.slice(page.indexOf("async toggleDataSource"), page.indexOf("qualityLabel("));
  assert.ok(!/delete|DELETE|scope/.test(toggle), "数据源控制不得夹带删除或范围修改");
});

test("the new hypium suite is registered in the ArkTS test list", () => {
  assert.match(testList, /import learnerWorldModelModelsTest from '\.\/ets\/agent\/LearnerWorldModelModels\.test';/);
  assert.match(testList, /learnerWorldModelModelsTest\(\);/);
});
