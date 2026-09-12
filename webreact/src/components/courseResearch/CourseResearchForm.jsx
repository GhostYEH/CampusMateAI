import { useState } from "react";
import { ASSISTANCE_MODE, assistanceModeLabel } from "../../data/agentContracts.js";

/**
 * CourseResearchForm — 课程研究提问表单。
 * 学生输入问题、选择课程与辅助模式。
 * 关键约束（任务 §5）：学术政策由后端裁决，前端不通过 mode 推断是否允许完整答案。
 * assistance_mode 只是学生意愿，最终是否提供 FULL_SOLUTION 由后端 academic_policy 决定。
 */
export default function CourseResearchForm({ courses = [], onSubmit, submitting = false, error = null }) {
  const [question, setQuestion] = useState("");
  const [courseId, setCourseId] = useState("");
  const [mode, setMode] = useState("EXPLAIN");
  const [allowWeb, setAllowWeb] = useState(true);

  function handleSubmit(event) {
    event.preventDefault();
    if (!question.trim() || submitting) return;
    onSubmit?.({
      question: question.trim(),
      course_id: courseId || null,
      assistance_mode: mode,
      source_policy: {
        course_material_priority: true,
        allow_web: allowWeb,
        allow_user_upload: false,
      },
    });
  }

  return (
    <form className="course-research-form" onSubmit={handleSubmit} aria-labelledby="cr-form-title">
      <h3 id="cr-form-title">提出课程问题</h3>
      {error && <p className="form-error" role="alert">{error.message || error}</p>}

      <label className="form-field">
        <span>问题</span>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={3}
          maxLength={500}
          placeholder="例如：解释梯度下降的学习率选择"
          aria-required="true"
          required
        />
      </label>

      <label className="form-field">
        <span>关联课程（可选）</span>
        <select value={courseId} onChange={(e) => setCourseId(e.target.value)}>
          <option value="">不指定课程</option>
          {courses.map((c) => (
            <option key={c.id} value={c.id}>{c.name || c.title || c.id}</option>
          ))}
        </select>
      </label>

      <fieldset className="form-mode">
        <legend>辅助模式（仅表达意愿，最终由学术政策裁决）</legend>
        {ASSISTANCE_MODE.map((m) => (
          <label key={m} className="mode-option">
            <input type="radio" name="assistance-mode" value={m} checked={mode === m} onChange={() => setMode(m)} />
            <span>{assistanceModeLabel(m)}</span>
          </label>
        ))}
      </fieldset>

      <label className="form-field checkbox-field">
        <input type="checkbox" checked={allowWeb} onChange={(e) => setAllowWeb(e.target.checked)} />
        <span>允许检索公开网络来源</span>
      </label>

      <button className="button button-primary" type="submit" disabled={submitting || !question.trim()}>
        {submitting ? "正在提交…" : "开始研究"}
      </button>
    </form>
  );
}