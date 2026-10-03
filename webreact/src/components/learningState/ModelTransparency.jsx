import { EmptyState } from './shared.jsx';

function ModelTransparency({ transparency }) {
  if (!transparency?.capabilities) return <EmptyState text="暂时没有模型透明度数据" />;
  return (
    <section className="ls-section ls-transparency" aria-label="模型透明度">
      <p className="ls-transparency__note">CampusMate-LM 的候选结果只作只读展示，不会修改你的正式学习状态、计划或待办。学习计划的自动调整只来自状态驱动干预：系统在观测窗结束后依据真实执行证据决定，且只有 <code>APPLIED</code> 才代表计划真的被替换。</p>
      {transparency.capabilities.map((cap) => (
        <article key={cap.capability_name} className="ls-cap-card">
          <h4>{CAPABILITY_LABEL[cap.capability_name] || cap.capability_name}</h4>
          <p className="ls-cap-card__method">生产方式：{cap.production_method}</p>
          <p className={`ls-cap-card__status ls-cap-card__status--${(cap.campusmate_lm_status || "").toLowerCase()}`}>
            {PROMOTION_LABEL[cap.campusmate_lm_status] || cap.campusmate_lm_status}
          </p>
          <p>质量门控：{cap.quality_gate_passed ? "通过" : "未通过"}</p>
          <p>性能门控：{cap.performance_measured ? (cap.performance_gate_passed ? "通过" : "未通过") : "真实设备性能尚未评测"}</p>
          <p>真实模型推理：{cap.uses_real_model_inference ? "是" : "否"}</p>
        </article>
      ))}
    </section>
  );
}

const CAPABILITY_LABEL = {
  learning_summary_v1: "学习摘要",
  read_only_tool_routing_v1: "只读工具路由",
  forecast_baseline_v1: "基线预测",
  simulation_baseline_v1: "方案模拟",
};

const PROMOTION_LABEL = {
  SHADOW_ONLY: "仅影子评测", BLOCKED: "已阻断", ELIGIBLE_FOR_CANARY: "可进入金丝雀", REVOKED: "已撤销",
};

export { ModelTransparency };
