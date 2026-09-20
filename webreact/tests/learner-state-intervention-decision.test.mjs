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
  DECISION_STATUS,
  DECISION_TONE,
  INTERVENTION_SCOPE,
  OBSERVED_OUTCOME_LABEL,
  PLAN_SWITCHED_LABEL,
  describeAdoption,
  describeInterventionDecision,
  describeInterventionScope,
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
          // 只有执行完成的决策才谈得上"已落地"，这里统一取终态。
          decision_status: "APPLIED",
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

describe("REPLAN 的计划切换状态必须按后端 decision_status 展示", () => {
  /**
   * `adaptive_replan_decisions.status` 描述"这次调整走到哪一步了"：
   * PENDING 还没开始、APPLYING 正在做、APPLIED 真的切换完成、FAILED 切换失败。
   * 计划只在 APPLIED 时才是新的，其余三种都必须说清楚"计划还没换"。
   */
  const CASES = {
    PENDING: { pattern: /尚未开始|准备/, applied: false },
    APPLYING: { pattern: /正在/, applied: false },
    APPLIED: { pattern: /已调整/, applied: true },
    FAILED: { pattern: /失败/, applied: false },
  };

  for (const [status, expectation] of Object.entries(CASES)) {
    it(`REPLAN + ${status} 如实反映计划是否已经切换`, () => {
      const view = describeInterventionDecision({
        outcome: {
          decision: "REPLAN",
          decision_status: status,
          suggested_adjustments: ["reduce_workload"],
        },
      });
      assert.equal(view.decision, "REPLAN");
      assert.equal(view.decisionStatus, status);
      assert.equal(view.applied, expectation.applied, `applied 必须与 ${status} 一致`);
      assert.match(view.label, expectation.pattern);
      if (!expectation.applied) {
        assert.notEqual(
          view.label, PLAN_SWITCHED_LABEL,
          `${status} 时计划尚未切换，不能显示"${PLAN_SWITCHED_LABEL}"`,
        );
      }
    });
  }

  it("只有 REPLAN + APPLIED 才允许出现'已调整学习计划'", () => {
    const decisions = ["CONTINUE", "WAIT_FOR_EVIDENCE", "REPLAN", "SUSPEND", "FUTURE_CODE"];
    const statuses = ["PENDING", "APPLYING", "APPLIED", "FAILED", null, undefined, "FUTURE_STATUS"];
    const claiming = [];
    for (const decision of decisions) {
      for (const decision_status of statuses) {
        const view = describeInterventionDecision({
          outcome: { decision, decision_status },
        });
        if (view.label === PLAN_SWITCHED_LABEL || view.applied === true) {
          claiming.push(`${decision}/${decision_status}`);
        }
      }
    }
    assert.deepEqual(claiming, ["REPLAN/APPLIED"], "只有这一种组合能声称计划已切换");
  });

  it("decision_status 缺失或未知时保守处理：绝不声称计划已切换", () => {
    for (const decision_status of [null, undefined, "", "FUTURE_STATUS"]) {
      const view = describeInterventionDecision({
        outcome: { decision: "REPLAN", decision_status },
      });
      assert.equal(view.applied, false, `未知状态 ${decision_status} 不能当作已切换`);
      assert.notEqual(view.label, PLAN_SWITCHED_LABEL);
      assert.match(view.label, /尚未开始|正在|待/);
    }
  });

  it("切换失败时明确说明按原计划继续，而不是静默显示成已调整", () => {
    const view = describeInterventionDecision({
      outcome: { decision: "REPLAN", decision_status: "FAILED" },
    });
    assert.equal(view.applied, false);
    assert.equal(view.tone, "warn");
    assert.match(view.detail ?? "", /原计划|未切换|保留/);
  });

  it("非 REPLAN 决定不受 decision_status 影响，仍展示各自的决定", () => {
    for (const decision of ["CONTINUE", "WAIT_FOR_EVIDENCE", "SUSPEND"]) {
      for (const decision_status of ["PENDING", "APPLYING", "APPLIED", "FAILED"]) {
        const view = describeInterventionDecision({ outcome: { decision, decision_status } });
        assert.equal(view.label, DECISION_LABEL[decision]);
        assert.equal(view.tone, DECISION_TONE[decision]);
        assert.equal(view.applied, false, "只有重规划才谈得上切换计划");
      }
    }
  });

  it("导出状态常量与后端 CHECK 约束一致", () => {
    assert.deepEqual(
      [...Object.values(DECISION_STATUS)].sort(),
      ["APPLIED", "APPLYING", "FAILED", "PENDING"],
    );
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

  it("页面把'计划是否已切换'作为可断言的展示状态暴露出来", () => {
    // 文案由投影模块决定，页面只渲染，不在页面里硬编码"已调整学习计划"。
    assert.doesNotMatch(pageSource, /已调整学习计划/);
    assert.match(pageSource, /data-plan-switched=\{String\(decision\.applied\)\}/);
    assert.match(pageSource, /data-decision-status=\{decision\.decisionStatus \?\? ""\}/);
  });
});

describe("干预归因范围：GOAL 与 PLAN 都进入闭环", () => {
  it("无目标普通计划必须写明归因范围是计划本身，且明确仍会调整计划", () => {
    const view = describeInterventionScope(INTERVENTION_SCOPE.PLAN);
    assert.equal(view.scope, "PLAN");
    assert.equal(view.label, "计划本身");
    // 关键：不能让学生误读成"不会跟进"。无目标计划同样观测、同样会安全替换计划。
    assert.match(view.detail, /同样会安全替换计划/);
    assert.doesNotMatch(view.detail, /仅观测|不会调整|不参与/);
  });

  it("绑定目标的干预写明按目标范围归因", () => {
    const view = describeInterventionScope(INTERVENTION_SCOPE.GOAL);
    assert.equal(view.scope, "GOAL");
    assert.equal(view.label, "学习目标");
    assert.match(view.detail, /按目标范围观测与评估/);
  });

  it("缺失或未知 scope_type 保守回退为 GOAL，不臆造新范围", () => {
    for (const value of [undefined, null, "", "SOMETHING_ELSE"]) {
      assert.equal(describeInterventionScope(value).scope, "GOAL");
    }
  });

  it("页面渲染归因范围，并把它挂在可断言的 data 属性上", () => {
    assert.match(pageSource, /describeInterventionScope\(intervention\.scope_type\)/);
    assert.match(pageSource, /data-intervention-scope=\{scope\.scope\}/);
    assert.match(pageSource, /<strong>归因范围：<\/strong>\{scope\.label\}/);
  });
});
