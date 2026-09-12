import { marked } from "marked";
import {
  academicPolicyLabel,
  assistanceModeLabel,
  allowsFullSolution,
} from "../../data/agentContracts.js";

/**
 * CourseResearchReport — 展示课程研究报告产物与学术政策裁决结果。
 *
 * 关键约束（任务 §5）：
 * - 学术政策由后端裁决，前端不通过 mode 推断是否允许完整答案。
 * - 显示 academic_policy 标签与最终可用辅助范围。
 * - 不展示 prompt、chain-of-thought 或敏感 trace。
 * - 冲突来源显示来源与时间，不静默合并。
 */
export default function CourseResearchReport({ run, artifact, artifactContent = null, onDownload, loading = false }) {
  if (loading && !run) {
    return (
      <section className="course-research-report state-card loading-state" aria-busy="true">
        <span className="loading-orb" aria-hidden="true" />
        <p>正在加载研究进展…</p>
      </section>
    );
  }
  if (!run) {
    return (
      <section className="course-research-report state-card empty-state">
        <p>提交问题后将展示研究进展与报告。</p>
      </section>
    );
  }

  const policy = run.academic_policy;
  const mode = run.assistance_mode;
  const fullSolutionAllowed = allowsFullSolution(policy);

  return (
    <section className="course-research-report" aria-labelledby="cr-report-title">
      <h3 id="cr-report-title">研究报告</h3>

      <dl className="report-meta">
        {policy && (
          <>
            <dt>学术政策</dt>
            <dd className={`policy-${policy}`}>{academicPolicyLabel(policy)}</dd>
          </>
        )}
        {mode && (
          <>
            <dt>请求模式</dt>
            <dd>{assistanceModeLabel(mode)}</dd>
          </>
        )}
        {policy && !fullSolutionAllowed && (
          <>
            <dt>可用帮助</dt>
            <dd>提示、讲解与点评（完整解答受政策限制）</dd>
          </>
        )}
      </dl>

      {artifactContent && (
        <div
          className="report-content"
          aria-label="报告正文"
          dangerouslySetInnerHTML={{ __html: renderMarkdown(artifactContent) }}
        />
      )}

      {!artifactContent && artifact && (
        <p className="report-pending">报告产物已生成，点击下方下载查看完整内容。</p>
      )}

      {!artifact && !artifactContent && run.status !== "SUCCEEDED" && run.status !== "PARTIAL" && (
        <p className="report-pending">研究进行中，完成后将在此展示报告。</p>
      )}

      {artifact && onDownload && (
        <button className="button button-secondary" type="button" onClick={() => onDownload(artifact)}>
          下载报告
        </button>
      )}
    </section>
  );
}

function renderMarkdown(text) {
  if (!text) return "";
  try {
    const html = marked.parse(text, { breaks: true, gfm: true });
    if (typeof DOMParser === "undefined") return String(text);
    const doc = new DOMParser().parseFromString(html, "text/html");
    doc.querySelectorAll("script,style,iframe,object,embed,form,link,meta").forEach((n) => n.remove());
    doc.querySelectorAll("*").forEach((n) => [...n.attributes].forEach((a) => {
      if (a.name.toLowerCase().startsWith("on")) n.removeAttribute(a.name);
    }));
    doc.querySelectorAll("a").forEach((n) => {
      try {
        const url = new URL(n.getAttribute("href"), window.location.href);
        if (!["http:", "https:"].includes(url.protocol)) n.removeAttribute("href");
        else { n.setAttribute("rel", "noreferrer noopener"); n.setAttribute("target", "_blank"); }
      } catch { n.removeAttribute("href"); }
    });
    return doc.body.innerHTML;
  } catch {
    return String(text || "");
  }
}