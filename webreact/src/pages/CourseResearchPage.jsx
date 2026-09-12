/**
 * CourseResearchPage — 课程研究 Agent 工作台（分栏布局）。
 *
 * 流程：提问 → 创建 run → 订阅 SSE → 查看报告产物。
 * - 学术政策由后端裁决，前端不通过 mode 推断（任务 §5）。
 * - 稳定 Idempotency-Key 保存在组件状态。
 * - 宽屏分栏，窄屏堆叠（≥320px）。
 * - 不展示 prompt、chain-of-thought、完整上下文或敏感 trace。
 */
import { useCallback, useEffect, useState } from "react";
import { PageFrame, Panel, SectionHeading, AsyncState } from "../components/Primitives.jsx";
import AgentErrorBoundary from "../components/agent/ErrorBoundary.jsx";
import RunProgress from "../components/agent/RunProgress.jsx";
import ArtifactViewer from "../components/agent/ArtifactViewer.jsx";
import CourseResearchForm from "../components/courseResearch/CourseResearchForm.jsx";
import CourseResearchReport from "../components/courseResearch/CourseResearchReport.jsx";
import { useAgentRun } from "../hooks/useAgentRun.js";
import * as api from "../data/agentRuntimeApi.js";
import * as baseApi from "../data/api.js";
import { itemsOf } from "../data/contracts.js";
import { createIdempotencyKey } from "../data/agentContracts.js";

export default function CourseResearchPage() {
  const [courses, setCourses] = useState([]);
  const [coursesLoading, setCoursesLoading] = useState(true);
  const [activeRunId, setActiveRunId] = useState(null);
  const [runMeta, setRunMeta] = useState(null);
  const [artifact, setArtifact] = useState(null);
  const [artifactContent, setArtifactContent] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [createKey, setCreateKey] = useState(() => createIdempotencyKey("cr_create"));

  const run = useAgentRun({ runId: activeRunId });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await baseApi.getCourses();
        if (!cancelled) setCourses(itemsOf(data));
      } catch { /* 课程可选 */ } finally {
        if (!cancelled) setCoursesLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const handleSubmit = useCallback(async (body) => {
    setSubmitting(true);
    setError(null);
    setArtifact(null);
    setArtifactContent(null);
    try {
      const result = await api.createCourseResearchRun({ ...body, idempotency_key: createKey }, createKey);
      setActiveRunId(result.run_id);
      setRunMeta(result);
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  }, [createKey]);

  useEffect(() => {
    if (!run.run?.artifact_ids?.length) return;
    const id = run.run.artifact_ids[0];
    if (artifact?.artifact_id === id) return;
    (async () => {
      try {
        const art = await api.getAgentArtifact(id);
        setArtifact(art);
        if (art?.download_url && art.mime_type === "text/markdown") {
          const resp = await baseApi.client.get(art.download_url, { responseType: "text" });
          setArtifactContent(resp.data);
        }
      } catch { /* 忽略产物加载错误 */ }
    })();
  }, [run.run, artifact]);

  const handleDownload = useCallback(async (art) => {
    if (!art?.download_url) return;
    const response = await baseApi.client.get(art.download_url, { responseType: "blob" });
    const url = URL.createObjectURL(response.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = `course-research-report.${art.mime_type === "text/markdown" ? "md" : "json"}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }, []);

  const mergedRun = run.run ? {
    ...run.run,
    ...(runMeta?.academic_policy ? { academic_policy: runMeta.academic_policy } : {}),
    ...(runMeta?.assistance_mode ? { assistance_mode: runMeta.assistance_mode } : {}),
  } : null;

  return (
    <PageFrame eyebrow="Agent 工作台" title="课程研究" description="在学术政策约束下检索课程资料并生成带引用的报告。">
      <AgentErrorBoundary>
        <div className="agent-workspace course-research-workspace split-pane">
          <Panel className="workspace-main pane-left">
            <SectionHeading title="提问" />
            <CourseResearchForm courses={courses} onSubmit={handleSubmit} submitting={submitting} error={error} />
            <AsyncState loading={coursesLoading} empty={null}>
              <RunProgress
                run={mergedRun}
                events={run.events}
                streamStatus={run.streamStatus}
                streamStatusLabel={run.streamStatusLabel}
                loading={run.loading}
                error={run.error}
                onCancel={() => run.cancel(createIdempotencyKey("cr_cancel"))}
              />
            </AsyncState>
          </Panel>

          <Panel className="workspace-side pane-right">
            <SectionHeading title="报告" />
            <CourseResearchReport
              run={mergedRun}
              artifact={artifact}
              artifactContent={artifactContent}
              onDownload={handleDownload}
              loading={run.loading}
            />
            {artifact && <ArtifactViewer artifact={artifact} onDownload={handleDownload} />}
          </Panel>
        </div>
      </AgentErrorBoundary>
    </PageFrame>
  );
}