import { useState } from "react";
import { createIdempotencyKey } from "../../data/agentContracts.js";

/**
 * FinalReviewCampaignForm — 创建期末复习活动。
 * 学生选择考试、设置每日容量与偏好。提交带稳定 Idempotency-Key。
 * 不假设空闲时间都是学习时间（设计 §8.1）。
 */
export default function FinalReviewCampaignForm({ exams = [], onSubmit, submitting = false, error = null }) {
  const [selectedExams, setSelectedExams] = useState([]);
  const [dailyMinutes, setDailyMinutes] = useState(120);
  const [restDays, setRestDays] = useState([]);
  const [intensity, setIntensity] = useState("balanced");
  const [key, setKey] = useState(() => createIdempotencyKey("fr_campaign"));

  function toggleExam(id) {
    setSelectedExams((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  function toggleRest(day) {
    setRestDays((prev) => (prev.includes(day) ? prev.filter((x) => x !== day) : [...prev, day]));
  }

  function handleSubmit(event) {
    event.preventDefault();
    if (selectedExams.length === 0 || submitting) return;
    onSubmit?.({
      exam_ids: selectedExams,
      daily_capacity_minutes: Number(dailyMinutes),
      rest_days: restDays,
      intensity,
      idempotency_key: key,
    });
  }

  return (
    <form className="final-review-form" onSubmit={handleSubmit} aria-labelledby="fr-form-title">
      <h3 id="fr-form-title">创建期末复习活动</h3>

      {error && <p className="form-error" role="alert">{error.message || error}</p>}

      <fieldset className="form-exams">
        <legend>选择考试（可多选）</legend>
        {exams.length === 0 ? (
          <p className="form-empty">暂无考试数据，请先在考试页录入。</p>
        ) : (
          <ul className="exam-list">
            {exams.map((exam) => (
              <li key={exam.id}>
                <label>
                  <input
                    type="checkbox"
                    checked={selectedExams.includes(exam.id)}
                    onChange={() => toggleExam(exam.id)}
                    aria-label={`选择考试 ${exam.title || exam.course_name || exam.id}`}
                  />
                  <span>{exam.title || exam.course_name || exam.id}</span>
                  {exam.exam_date && <small>{exam.exam_date}</small>}
                </label>
              </li>
            ))}
          </ul>
        )}
      </fieldset>

      <label className="form-field">
        <span>每日可用学习时间（分钟）</span>
        <input
          type="range"
          min={30}
          max={480}
          step={15}
          value={dailyMinutes}
          onChange={(e) => setDailyMinutes(Number(e.target.value))}
          aria-valuemin={30}
          aria-valuemax={480}
          aria-valuenow={dailyMinutes}
        />
        <output>{dailyMinutes} 分钟</output>
      </label>

      <fieldset className="form-rest">
        <legend>休息日（不安排复习）</legend>
        {["周一", "周二", "周三", "周四", "周五", "周六", "周日"].map((day) => (
          <label key={day} className="rest-day">
            <input type="checkbox" checked={restDays.includes(day)} onChange={() => toggleRest(day)} />
            <span>{day}</span>
          </label>
        ))}
      </fieldset>

      <label className="form-field">
        <span>强度偏好</span>
        <select value={intensity} onChange={(e) => setIntensity(e.target.value)}>
          <option value="balanced">均衡</option>
          <option value="intensive">集中冲刺</option>
          <option value="gentle">循序渐进</option>
        </select>
      </label>

      <button className="button button-primary" type="submit" disabled={submitting || selectedExams.length === 0}>
        {submitting ? "正在创建…" : "创建活动"}
      </button>
    </form>
  );
}