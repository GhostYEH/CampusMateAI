/**
 * 学习预测页面 — Phase 9F
 *
 * 展示预测型学生世界模型：
 * 知识掌握预测 → 表现预测 → 学习速度 → 反事实模拟 → 预测评测
 *
 * 中性产品语言，避免心理画像/能力判定等负面表述。
 */
import { useCallback, useMemo, useRef, useState } from "react";
import * as api from "../data/learnerStateApi.js";
import { client } from "../data/api.js";

const FORECAST_TREND_LABEL = {
  improving: "稳步提升",
  steady: "保持稳定",
  declining: "有所下降",
  insufficient_evidence: "证据不足",
};

const VELOCITY_TREND_LABEL = {
  accelerating: "加速进步",
  steady: "稳定学习",
  decelerating: "节奏放缓",
  insufficient_evidence: "证据不足",
};

const SCORE_BAND_LABEL = {
  likely_pass: "大概率通过",
  likely_partial: "部分通过",
  likely_fail: "需要更多练习",
  insufficient_evidence: "证据不足",
};

const INTERVENTION_TYPES = [
  { value: "additional_practice", label: "额外练习" },
  { value: "remediation", label: "针对性补救" },
  { value: "review_session", label: "复习巩固" },
];

function useAsync(fn, deps) {
  const [state, setState] = useState({ loading: true, data: null, error: null });
  const mounted = useRef(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const run = useCallback(() => {
    setState((s) => ({ ...s, loading: true, error: null }));
    Promise.resolve(fnRef.current())
      .then((data) => mounted.current && setState({ loading: false, data, error: null }))
      .catch((error) => mounted.current && setState({ loading: false, data: null, error }));
  }, deps);
  useRef(() => () => { mounted.current = false; });
  return { ...state, reload: run };
}

function Spinner() {
  return <div className="pred-spinner">加载中…</div>;
}

function ErrorBar({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="pred-error">
      <span>{error.message || "加载失败"}</span>
      {onRetry && <button onClick={onRetry} className="pred-error__retry">重试</button>}
    </div>
  );
}

function EmptyState({ children }) {
  return <div className="pred-empty">{children}</div>;
}

function pct(v) {
  return `${Math.round(v * 100)}%`;
}

function TrendBadge({ trend, labelMap }) {
  const label = labelMap[trend] || trend;
  const cls = trend === "improving" || trend === "accelerating" ? "up" :
    trend === "declining" || trend === "decelerating" ? "down" : "flat";
  return <span className={`pred-trend pred-trend--${cls}`}>{label}</span>;
}

export default function PredictionPage() {
  const [courseId, setCourseId] = useState("");
  const [courses, setCourses] = useState([]);
  const [coursesLoading, setCoursesLoading] = useState(true);
  const [simForm, setSimForm] = useState({
    intervention_type: "additional_practice",
    knowledge_component_code: "c.pointer.basics",
    additional_practice_count: 5,
    expected_score: 80,
    misconception_code: null,
  });
  const [simResult, setSimResult] = useState(null);
  const [simLoading, setSimLoading] = useState(false);
  const [simError, setSimError] = useState(null);

  useRef(() => {
    client.get("/courses").then((r) => r.data).then((data) => {
      const items = data?.items || data || [];
      setCourses(Array.isArray(items) ? items : []);
      setCoursesLoading(false);
    }).catch(() => setCoursesLoading(false));
  });

  const effectiveCourseId = courseId || (courses[0]?.id || "");

  const predictions = useAsync(
    () => effectiveCourseId ? api.getPredictions(effectiveCourseId) : Promise.resolve({ items: [] }),
    [effectiveCourseId],
  );

  const evaluation = useAsync(
    () => effectiveCourseId ? api.getPredictionEvaluation(effectiveCourseId) : Promise.resolve(null),
    [effectiveCourseId],
  );

  const forecastSnapshots = useMemo(
    () => (predictions.data?.items || []).filter((s) => s.state_type === "knowledge_mastery_forecast"),
    [predictions.data],
  );
  const performanceSnapshots = useMemo(
    () => (predictions.data?.items || []).filter((s) => s.state_type === "performance_prediction"),
    [predictions.data],
  );
  const velocitySnapshots = useMemo(
    () => (predictions.data?.items || []).filter((s) => s.state_type === "learning_velocity"),
    [predictions.data],
  );

  const handleSimulate = useCallback(async () => {
    if (!effectiveCourseId) return;
    setSimLoading(true);
    setSimError(null);
    try {
      const result = await api.simulateCounterfactual(effectiveCourseId, simForm);
      setSimResult(result);
    } catch (err) {
      setSimError(err);
    } finally {
      setSimLoading(false);
    }
  }, [effectiveCourseId, simForm]);

  return (
    <div className="pred-page">
      <header className="pred-page__header">
        <h1>学习预测</h1>
        <p className="pred-page__subtitle">基于练习历史的确定性预测，诚实表达不确定性</p>
      </header>

      {coursesLoading ? (
        <Spinner />
      ) : courses.length > 0 ? (
        <div className="pred-course-select">
          <label>选择课程</label>
          <select value={effectiveCourseId} onChange={(e) => setCourseId(e.target.value)}>
            {courses.map((c) => (
              <option key={c.id} value={c.id}>{c.name || c.id}</option>
            ))}
          </select>
        </div>
      ) : null}

      {!effectiveCourseId ? (
        <EmptyState>暂无课程数据，请先关联课程</EmptyState>
      ) : (
        <>
          <section className="pred-section">
            <h2 className="pred-section__title">掌握度预测</h2>
            {predictions.loading ? <Spinner /> : predictions.error ? (
              <ErrorBar error={predictions.error} onRetry={predictions.reload} />
            ) : forecastSnapshots.length === 0 ? (
              <EmptyState>练习数据不足，暂无预测</EmptyState>
            ) : (
              <div className="pred-cards">
                {forecastSnapshots.map((snap) => (
                  <div key={snap.snapshot_id} className="pred-card">
                    <div className="pred-card__header">
                      <span className="pred-card__kc">{snap.value.knowledge_component_code}</span>
                      <TrendBadge trend={snap.value.trend} labelMap={FORECAST_TREND_LABEL} />
                    </div>
                    <div className="pred-card__body">
                      <div className="pred-metric">
                        <span className="pred-metric__label">当前掌握</span>
                        <span className="pred-metric__value">{pct(snap.value.current_estimate)}</span>
                      </div>
                      <div className="pred-metric">
                        <span className="pred-metric__label">7天预测</span>
                        <span className="pred-metric__value">{pct(snap.value.forecast_7d)}</span>
                      </div>
                      <div className="pred-metric">
                        <span className="pred-metric__label">30天预测</span>
                        <span className="pred-metric__value">{pct(snap.value.forecast_30d)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="pred-section">
            <h2 className="pred-section__title">表现预测</h2>
            {!predictions.loading && performanceSnapshots.length > 0 ? (
              <div className="pred-cards">
                {performanceSnapshots.map((snap) => (
                  <div key={snap.snapshot_id} className="pred-card">
                    <div className="pred-card__header">
                      <span className="pred-card__kc">{snap.value.knowledge_component_code}</span>
                      <span className="pred-badge">{SCORE_BAND_LABEL[snap.value.predicted_score_band] || snap.value.predicted_score_band}</span>
                    </div>
                    <div className="pred-card__body">
                      <div className="pred-metric">
                        <span className="pred-metric__label">通过概率</span>
                        <span className="pred-metric__value">{pct(snap.value.predicted_pass_probability)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState>暂无表现预测数据</EmptyState>
            )}
          </section>

          <section className="pred-section">
            <h2 className="pred-section__title">学习速度</h2>
            {!predictions.loading && velocitySnapshots.length > 0 ? (
              <div className="pred-cards">
                {velocitySnapshots.map((snap) => (
                  <div key={snap.snapshot_id} className="pred-card">
                    <div className="pred-card__header">
                      <span className="pred-card__kc">{snap.value.knowledge_component_code}</span>
                      <TrendBadge trend={snap.value.trend} labelMap={VELOCITY_TREND_LABEL} />
                    </div>
                    <div className="pred-card__body">
                      <div className="pred-metric">
                        <span className="pred-metric__label">一致性</span>
                        <span className="pred-metric__value">{pct(snap.value.consistency)}</span>
                      </div>
                      <div className="pred-metric">
                        <span className="pred-metric__label">证据数</span>
                        <span className="pred-metric__value">{snap.value.evidence_count}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState>暂无学习速度数据</EmptyState>
            )}
          </section>

          <section className="pred-section pred-section--sim">
            <h2 className="pred-section__title">反事实模拟</h2>
            <p className="pred-section__desc">假设采取干预措施后的预测变化，不会修改实际学习状态</p>
            <div className="pred-sim-form">
              <label>
                <span>干预类型</span>
                <select value={simForm.intervention_type}
                  onChange={(e) => setSimForm({ ...simForm, intervention_type: e.target.value })}>
                  {INTERVENTION_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>知识点</span>
                <input value={simForm.knowledge_component_code}
                  onChange={(e) => setSimForm({ ...simForm, knowledge_component_code: e.target.value })} />
              </label>
              {simForm.intervention_type === "additional_practice" && (
                <>
                  <label>
                    <span>练习次数</span>
                    <input type="number" min="0" max="100" value={simForm.additional_practice_count}
                      onChange={(e) => setSimForm({ ...simForm, additional_practice_count: parseInt(e.target.value) || 0 })} />
                  </label>
                  <label>
                    <span>预期得分</span>
                    <input type="number" min="0" max="100" value={simForm.expected_score}
                      onChange={(e) => setSimForm({ ...simForm, expected_score: parseFloat(e.target.value) || 0 })} />
                  </label>
                </>
              )}
              <button onClick={handleSimulate} disabled={simLoading} className="pred-btn pred-btn--primary">
                {simLoading ? "模拟中…" : "运行模拟"}
              </button>
            </div>
            {simError && <ErrorBar error={simError} />}
            {simResult && (
              <div className="pred-sim-result">
                {simResult.deltas.length === 0 ? (
                  <EmptyState>模拟未产生变化</EmptyState>
                ) : (
                  <table className="pred-sim-table">
                    <thead>
                      <tr>
                        <th>知识点</th>
                        <th>基线7天预测</th>
                        <th>模拟后7天预测</th>
                        <th>掌握度变化</th>
                      </tr>
                    </thead>
                    <tbody>
                      {simResult.deltas.map((d) => (
                        <tr key={d.knowledge_component_code}>
                          <td>{d.knowledge_component_code}</td>
                          <td>{pct(d.baseline_forecast_7d)}</td>
                          <td>{pct(d.counterfactual_forecast_7d)}</td>
                          <td className={d.mastery_delta > 0 ? "pos" : d.mastery_delta < 0 ? "neg" : ""}>
                            {d.mastery_delta > 0 ? "+" : ""}{pct(d.mastery_delta)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </section>

          <section className="pred-section pred-section--eval">
            <h2 className="pred-section__title">预测评测</h2>
            {evaluation.loading ? <Spinner /> : evaluation.error ? (
              <ErrorBar error={evaluation.error} onRetry={evaluation.reload} />
            ) : evaluation.data ? (
              <div className="pred-eval">
                <div className="pred-eval__metrics">
                  <div className="pred-metric">
                    <span className="pred-metric__label">准确率</span>
                    <span className="pred-metric__value">{pct(evaluation.data.accuracy)}</span>
                  </div>
                  <div className="pred-metric">
                    <span className="pred-metric__label">PR-AUC</span>
                    <span className="pred-metric__value">{evaluation.data.pr_auc.toFixed(3)}</span>
                  </div>
                  <div className="pred-metric">
                    <span className="pred-metric__label">Log Loss</span>
                    <span className="pred-metric__value">{evaluation.data.log_loss.toFixed(3)}</span>
                  </div>
                  <div className="pred-metric">
                    <span className="pred-metric__label">Brier Score</span>
                    <span className="pred-metric__value">{evaluation.data.brier_score.toFixed(3)}</span>
                  </div>
                </div>
                <div className={`pred-eval__gate ${evaluation.data.truthfulness_gate_passed ? "pass" : "fail"}`}>
                  {evaluation.data.truthfulness_gate_passed ? "真实性门禁通过" : "真实性门禁未通过"}
                  {evaluation.data.gate_failure_reasons.length > 0 && (
                    <span className="pred-eval__reasons">
                      {evaluation.data.gate_failure_reasons.join("、")}
                    </span>
                  )}
                </div>
              </div>
            ) : (
              <EmptyState>暂无评测数据</EmptyState>
            )}
          </section>
        </>
      )}
    </div>
  );
}