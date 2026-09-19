/**
 * 干预闭环"系统决定"的展示契约。
 *
 * 关键约束：前端只能读后端**持久化**的决策（adaptive_replan_decisions），
 * 不允许按 delta 或观测结果去猜系统决定。因此这里逐条锁死六种情形：
 * CONTINUE / WAIT_FOR_EVIDENCE / REPLAN / SUSPEND / 请求失败 / 决策为 null。
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import {
  DECISION_LABEL,
  DECISION_STATE,
  DECISION_TONE,
  OBSERVED_OUTCOME_LABEL,
  describeAdoption,
  describeInterventionDecision,
  describeObservedOutcome,
} from "../src/data/interventionDecisionView.js";

const pageSource = await readFile(
  new URL("../src/pages/LearningStatePage.jsx", import.meta.url), "utf8",
);

describe("持久化决策的五态展示", () => {
  for (const decision of ["CONTINUE", "WAIT_FOR_EVIDENCE", "REPLAN", "SUSPEND"]) {
    it(`decision=${decision} 时展示后端落库的决定，而不是按状态差值推测`, () => {
      const view = describeInterventionDecision({
        outcome: {
          decision,
          decision_reason_codes: [`reason_${decision.toLowerCase()}`],
          suggested_adjustments: decision === "REPLAN" ? ["reinforce_foundation"] : [],
          observed_outcome: "DECLINED",
        },
      });
      assert.equal(view.state, DECISION_STATE.DECIDED);
      assert.equal(view.decision, decision);
      assert.equal(view.label, DECISION_LABEL[decision]);
      assert.equal(view.tone, DECISION_TONE[decision]);
      assert.deepEqual(view.reasonCodes, [`reason_${decision.toLowerCase()}`]);
      // 观测结果同样来自后端，不由前端按 delta 反推
      assert.equal(view.observedOutcome, "DECLINED");
      assert.equal(view.observedOutcomeLabel, OBSERVED_OUTCOME_LABEL.DECLINED);
    });
  }

  it("REPLAN 展示真实调整项，SUSPEND/CONTINUE 不展示调整项", () => {
    const replan = describeInterventionDecision({
      outcome: { decision: "REPLAN", suggested_adjustments: ["lower_challenge", "reduce_workload"] },
    });
    assert.deepEqual(replan.adjustments, ["lower_challenge", "reduce_workload"]);

    const suspend = describeInterventionDecision({
      outcome: { decision: "SUSPEND", suggested_adjustments: [] },
    });
    assert.deepEqual(suspend.adjustments, []);
  });

  it("decision 为 null 时明确说明'尚无系统决定'，不冒充'证据不足'", () => {
    const view = describeInterventionDecision({
      outcome: { decision: null, observed_outcome: "INSUFFICIENT_EVIDENCE" },
    });
    assert.equal(view.state, DECISION_STATE.PENDING);
    assert.equal(view.decision, null);
    assert.match(view.detail, /观测窗口/);
    assert.notEqual(view.label, OBSERVED_OUTCOME_LABEL.INSUFFICIENT_EVIDENCE);
  });

  it("请求失败时给出可重试的错误态，且不编造任何决定", () => {
    const view = describeInterventionDecision({ error: new Error("网络不可用"), outcome: null });
    assert.equal(view.state, DECISION_STATE.UNAVAILABLE);
    assert.equal(view.decision, null);
    assert.equal(view.tone, "warn");
    assert.equal(view.detail, "网络不可用");
  });

  it("加载中与响应缺失都不得落到'已决定'", () => {
    assert.equal(describeInterventionDecision({ loading: true }).state, DECISION_STATE.LOADING);
    assert.equal(describeInterventionDecision({ outcome: null }).state, DECISION_STATE.UNAVAILABLE);
    assert.equal(describeInterventionDecision({}).state, DECISION_STATE.UNAVAILABLE);
  });

  it("未知决策码原样透出，不静默降级成某个已知决定", () => {
    const view = describeInterventionDecision({ outcome: { decision: "FUTURE_CODE" } });
    assert.equal(view.decision, "FUTURE_CODE");
    assert.equal(view.label, "FUTURE_CODE");
  });
});

describe("执行采纳与观测文案", () => {
  it("缺失采纳信号与'尚未开始'是两件事", () => {
    assert.equal(describeAdoption(null), "尚未开始");
    assert.equal(describeAdoption("COMPLETED"), "计划已完成");
    assert.equal(describeAdoption("IN_PROGRESS"), "计划执行中");
    assert.equal(describeAdoption("UNAVAILABLE"), "暂时取不到执行数据");
  });

  it("缺失观测结论时不冒充'证据不足'", () => {
    assert.equal(describeObservedOutcome(null), "尚未产生观测结论");
    assert.equal(describeObservedOutcome("IMPROVED"), "观测到改善");
    assert.equal(describeObservedOutcome("INSUFFICIENT_EVIDENCE"), "证据不足");
  });
});

describe("页面接线", () => {
  it("页面使用纯函数投影，并传入 loading / error / 重试回调", () => {
    assert.match(pageSource, /describeInterventionDecision\(\{ outcome, loading, error \}\)/);
    assert.match(pageSource, /loading=\{interventionOutcome\.loading\}/);
    assert.match(pageSource, /error=\{interventionOutcome\.error\}/);
    assert.match(pageSource, /onRetry=\{interventionOutcome\.reload\}/);
  });

  it("页面不再按 observed_outcome 猜测系统决定", () => {
    // 旧写法把非 IMPROVED 一律渲染成"证据不足"，且把决定退化成"尚无持久化决策"
    assert.doesNotMatch(pageSource, /IMPROVED \? "观测到改善" : "证据不足"/);
    assert.doesNotMatch(pageSource, /尚无持久化决策/);
    assert.doesNotMatch(pageSource, /decisionLabel\[outcome\.decision\]/);
  });

  it("决定徽标带有可断言的展示状态", () => {
    assert.match(pageSource, /data-decision-state=\{decision\.state\}/);
    assert.match(pageSource, /ls-decision--\$\{decision\.tone\}/);
  });
});
