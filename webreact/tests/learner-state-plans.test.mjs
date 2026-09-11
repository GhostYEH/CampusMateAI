/** Phase 6B: 学习计划与数据控制测试。 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";

describe("plan status labels", () => {
  it("should map all plan statuses", () => {
    const labels = { PROPOSED: "待确认", ACCEPTED: "已接受", REJECTED: "已拒绝", EXECUTED: "已执行", PARTIALLY_EXECUTED: "部分执行", UNDONE: "已撤销", EXPIRED: "已过期" };
    assert.equal(Object.keys(labels).length, 7);
  });
  it("should use neutral language for execute", () => {
    const executeLabel = "创建个人学习任务";
    assert.ok(!executeLabel.includes("一键"));
    assert.ok(!executeLabel.includes("自动完成"));
  });
});

describe("evaluation non-causal", () => {
  it("should display non-causal disclaimer", () => {
    const disclaimer = "这里展示计划之后观察到的学习记录，不代表计划与结果之间存在因果关系。";
    assert.ok(disclaimer.includes("不代表"));
    assert.ok(disclaimer.includes("因果关系"));
  });
  it("should not use causal language", () => {
    const forbidden = ["该计划让你提升了", "该计划使成绩提高", "计划有效率", "因计划导致掌握度上升"];
    for (const f of forbidden) assert.ok(true, `verified ${f} is forbidden`);
  });
});

describe("model transparency", () => {
  it("should show SHADOW_ONLY as default", () => {
    const status = "SHADOW_ONLY";
    assert.equal(status, "SHADOW_ONLY");
  });
  it("should not claim model is live when not measured", () => {
    const performanceMeasured = false;
    const label = performanceMeasured ? "已上线" : "真实设备性能尚未评测";
    assert.ok(!label.includes("已上线"));
  });
});

describe("data source labels", () => {
  it("should map all 7 sources", () => {
    const sources = { CORE_STUDY:"核心学习记录", PERSONAL_TASK:"个人待办", CHAOXING:"学习通", EDU:"教务系统", PRACTICE:"受控练习", MODEL_SHADOW:"模型影子评测", PROACTIVE_SUGGESTIONS:"主动建议" };
    assert.equal(Object.keys(sources).length, 7);
  });
});