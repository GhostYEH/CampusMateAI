import { useState } from "react";
import { createIdempotencyKey } from "../../data/agentContracts.js";

/**
 * NoticeWorkflowForm — 粘贴通知文本并创建 workflow。
 *
 * 关键约束（任务 §6）：
 * - 用户粘贴文本时先 POST /notices/manual 得到 server notice_id，再创建 workflow。
 * - 不把旧的"提取后直接 createTask"偷偷作为自动执行路径。
 * - 稳定 Idempotency-Key 保存在组件状态，重复点击不重复写入。
 * - NoticeCenter 既有行为保留，本表单是新增的受控流程入口。
 */
export default function NoticeWorkflowForm({ onSubmit, submitting = false, error = null }) {
  const [content, setContent] = useState("");
  const [sourceLabel, setSourceLabel] = useState("");
  const [manualKey] = useState(() => createIdempotencyKey("notice_manual"));
  const [workflowKey] = useState(() => createIdempotencyKey("notice_workflow"));

  function handleSubmit(event) {
    event.preventDefault();
    if (!content.trim() || submitting) return;
    onSubmit?.({
      content: content.trim(),
      source_label: sourceLabel.trim() || null,
      manual_key: manualKey,
      workflow_key: workflowKey,
    });
  }

  return (
    <form className="notice-workflow-form" onSubmit={handleSubmit} aria-labelledby="nw-form-title">
      <h3 id="nw-form-title">把通知变成可跟踪的流程</h3>
      {error && <p className="form-error" role="alert">{error.message || error}</p>}

      <label className="form-field">
        <span>通知内容</span>
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={5}
          maxLength={2000}
          placeholder="粘贴校园通知、教务公告或 Chaoxing 消息原文"
          aria-required="true"
          required
        />
      </label>

      <label className="form-field">
        <span>来源备注（可选）</span>
        <input
          type="text"
          value={sourceLabel}
          onChange={(e) => setSourceLabel(e.target.value)}
          maxLength={60}
          placeholder="例如：教务处公告 / 班群通知"
        />
      </label>

      <button className="button button-primary" type="submit" disabled={submitting || !content.trim()}>
        {submitting ? "正在创建…" : "创建流程"}
      </button>

      <p className="form-note">
        提交后将先在服务端登记一条手动通知，再生成可跟踪的流程。不会自动代你提交作业或登录教务系统。
      </p>
    </form>
  );
}