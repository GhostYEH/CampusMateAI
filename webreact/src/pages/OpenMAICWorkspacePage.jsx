import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import * as api from "../data/api.js";
import { AsyncState, BackLink, Button, PageFrame, Panel, SectionHeading } from "../components/Primitives.jsx";
import { Icon } from "../components/Icon.jsx";
import StageEditorPanel from "../components/openmaic/StageEditorPanel.jsx";
import StagePlayerPanel from "../components/openmaic/StagePlayerPanel.jsx";
import ProviderToolsPanel from "../components/openmaic/ProviderToolsPanel.jsx";
import { normalizeStageList, normalizeWorkspaceList } from "../features/openmaic/workspaceModel.js";
import { describeFusionState } from "../features/openmaic/homeModel.js";
import { filenameFromContentDisposition } from "../features/openmaic/archiveModel.js";
import { normalizeSelectedRoleIds, selectedRoles } from "../features/openmaic/roleModel.js";
import { formatDateTime } from "../utils/date.js";

const MODES = [["slide", "幻灯片"], ["quiz", "测验"], ["interactive", "互动课堂"], ["pbl", "项目式学习"], ["simulation", "模拟"], ["diagram", "图示"], ["code", "代码练习"], ["game", "游戏"], ["visualization3d", "3D 可视化"], ["procedural-skill", "程序技能"]];
const dateText = (value) => formatDateTime(value, { dateStyle: "medium", timeStyle: "short" }, "时间待定");
const errorText = (error, fallback = "工作台加载失败，请重试") => error?.response?.data?.detail || error?.response?.data?.message || error?.message || fallback;

function saveBlob(blob, filename) {
  if (typeof document === "undefined" || typeof URL === "undefined") return;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Chrome starts blob downloads asynchronously. Releasing it in the same task
  // can cancel a valid download in browsers that observe the download event a
  // little later (including real automation browsers).
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function StageExportActions({ courseId, workspaceId, stage, canExportPptx }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!stage) return null;
  async function exportPptx() {
    if (busy) return;
    setBusy(true); setError("");
    try {
      const result = await api.exportOpenMAICStageFormat(courseId, workspaceId, stage.id, "pptx");
      saveBlob(result.blob, filenameFromContentDisposition(result.disposition) || `${stage.title}.pptx`);
    } catch (failure) {
      setError(errorText(failure, "PPTX 导出失败，请稍后重试"));
    } finally { setBusy(false); }
  }
  return <div className="openmaic-stage-export" aria-label="场景导出">
    {canExportPptx ? <Button type="button" variant="secondary" icon="PhDownloadSimple" disabled={busy} onClick={exportPptx}>{busy ? "导出中…" : "导出 PPTX"}</Button> : <span className="muted-copy">PPTX 导出未启用</span>}
    {error ? <span className="openmaic-hint openmaic-hint--error" role="alert">{error}</span> : null}
  </div>;
}

export default function OpenMAICWorkspacePage() {
  const { courseId, workspaceId } = useParams();
  const [searchParams] = useSearchParams();
  const launchPrompt = searchParams.get("prompt")?.trim() || "";
  const launchRoleMode = searchParams.get("mode") === "auto" ? "auto" : "preset";
  const launchRoleIds = normalizeSelectedRoleIds((searchParams.get("roles") || "").split(",").filter(Boolean));
  const [workspace, setWorkspace] = useState(null); const [stages, setStages] = useState([]); const [selectedStageId, setSelectedStageId] = useState("");
  const [loading, setLoading] = useState(true); const [error, setError] = useState(""); const [notice, setNotice] = useState("");
  const [providerStatus, setProviderStatus] = useState(null);
  const [fusionStatus, setFusionStatus] = useState(null);
  const [mode, setMode] = useState("slide"); const [prompt, setPrompt] = useState(""); const [job, setJob] = useState(null); const [busy, setBusy] = useState(false); const [playing, setPlaying] = useState(false);
  const epoch = useRef(0); const polling = useRef(null);
  const launchStarted = useRef(false);

  const load = useCallback(async () => {
    const mine = ++epoch.current; setLoading(true); setError("");
    try {
      const [workspacePayload, stagePayload] = await Promise.all([api.getOpenMAICWorkspace(courseId, workspaceId), api.listOpenMAICStages(courseId, workspaceId, { limit: 50 })]);
      if (mine !== epoch.current) return;
      const nextWorkspace = normalizeWorkspaceList({ items: [workspacePayload] })[0] || null; const nextStages = normalizeStageList(stagePayload);
      setWorkspace(nextWorkspace); setStages(nextStages); setSelectedStageId((current) => nextStages.some((stage) => stage.id === current) ? current : nextStages[0]?.id || "");
    } catch (failure) { if (mine !== epoch.current) return; setWorkspace(null); setStages([]); setError(errorText(failure)); }
    finally { if (mine === epoch.current) setLoading(false); }
  }, [courseId, workspaceId]);

  const loadProviderStatus = useCallback(async () => {
    try { setProviderStatus(await api.getOpenMAICProviderStatus()); }
    catch { setProviderStatus(null); }
  }, []);

  const loadFusionStatus = useCallback(async () => {
    try { setFusionStatus(await api.getOpenMAICFusionStatus()); }
    catch { setFusionStatus(null); }
  }, []);

  useEffect(() => { setJob(null); setPlaying(false); void load(); void loadProviderStatus(); void loadFusionStatus(); return () => { epoch.current += 1; if (polling.current) window.clearTimeout(polling.current); }; }, [load, loadProviderStatus, loadFusionStatus]);

  useEffect(() => {
    // A refreshed deep link may still carry the original prompt, but an
    // already populated workspace is the durable proof that the launch ran.
    // Do not enqueue the same classroom again just because the browser reloaded.
    if (loading || !workspace || !launchPrompt || stages.length > 0 || launchStarted.current) return;
    launchStarted.current = true;
    setPrompt(launchPrompt);
    void generatePrompt(launchPrompt);
  }, [loading, workspace, stages.length, launchPrompt]);

  const pollJob = useCallback(async (jobId) => {
    try {
      const current = await api.getOpenMAICJob(courseId, jobId); if (current?.id !== jobId) return; setJob(current);
      if (["queued", "running"].includes(current.status)) polling.current = window.setTimeout(() => void pollJob(jobId), 800);
      else if (current.status === "completed") { setNotice("学习内容已生成，并已写入当前工作台。"); await load(); }
    } catch (failure) { setError(errorText(failure, "生成进度读取失败")); }
  }, [courseId, load]);

  async function generatePrompt(value) {
    const normalized = String(value || "").trim(); if (!normalized || busy) return; setBusy(true); setError(""); setNotice("");
    try { const result = await api.generateOpenMAICStage(courseId, workspaceId, { mode, prompt: normalized, roleMode: launchRoleMode, selectedRoleIds: launchRoleIds, idempotencyKey: api.newIdempotencyKey() }); setJob(result.job || null); setPrompt(""); await load(); if (result.job?.id && result.job.status !== "completed") void pollJob(result.job.id); else setNotice("学习内容已生成，并已写入当前工作台。"); }
    catch (failure) { setError(errorText(failure, "生成失败，原工作台内容未改变")); } finally { setBusy(false); }
  }
  async function generate(event) { event.preventDefault(); await generatePrompt(prompt); }
  async function cancelJob() { if (!job?.id) return; setBusy(true); try { setJob(await api.cancelOpenMAICJob(courseId, job.id)); setNotice("已请求中断生成。"); } catch (failure) { setError(errorText(failure, "中断失败")); } finally { setBusy(false); } }
  async function retryJob() { if (!job?.id) return; setBusy(true); try { const next = await api.retryOpenMAICJob(courseId, job.id); setJob(next); void pollJob(next.id); } catch (failure) { setError(errorText(failure, "重试失败")); } finally { setBusy(false); } }

  const selectedStage = useMemo(() => stages.find((stage) => stage.id === selectedStageId) || null, [stages, selectedStageId]);
  const jobBusy = job && ["queued", "running"].includes(job.status);
  return <PageFrame eyebrow="OpenMAIC / Workspace" title={workspace?.name || "学习工作台"} description={workspace?.description || "课程内容、场景编辑与播放"} actions={<><BackLink to="/courses">返回课程</BackLink><Button variant="secondary" icon="PhArrowClockwise" onClick={load} disabled={loading}>刷新</Button></>}>
    <AsyncState loading={loading} error={error} onRetry={load}><div className="openmaic-workspace-page">
      {notice ? <div className="page-notice notice-info" role="status">{notice}</div> : null}
      {launchPrompt ? <p className="openmaic-launch-context" role="status">{launchRoleMode === "auto" ? "自动生成角色" : `已选择角色：${selectedRoles(launchRoleIds).map((role) => role.name).join("、")}`}</p> : null}
      <Panel className="openmaic-generation-panel"><SectionHeading title="创建学习内容" detail="生成结果会写入当前 workspace，服务不可用时不会伪造内容。" /><form className="openmaic-command" onSubmit={generate}><label className="openmaic-command__input"><Icon name="PhSparkle" size={18} /><input value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="例如：讲解函数极限的直觉、定义和一个例题" maxLength={2000} aria-label="学习内容主题" /></label><select value={mode} onChange={(event) => setMode(event.target.value)} aria-label="学习内容类型">{MODES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><Button type="submit" disabled={busy || !prompt.trim()}>{busy ? "提交中…" : "生成"}</Button></form>{job ? <div className="openmaic-job-status" role="status"><span>{job.status === "completed" ? "已完成" : job.status === "cancelled" ? "已中断" : job.status === "failed" ? "失败" : "生成中"}</span><strong>{Number(job.progress) || 0}%</strong>{jobBusy ? <Button variant="quiet" disabled={busy} onClick={cancelJob}>中断</Button> : null}{["failed", "cancelled"].includes(job.status) ? <Button variant="quiet" disabled={busy} onClick={retryJob}>重试</Button> : null}</div> : null}</Panel>
      <div className="openmaic-workspace-page__grid"><Panel><SectionHeading title="场景目录" detail={`${stages.length} 个内容`} />{stages.length ? <ol className="openmaic-stage-browser__list">{stages.map((stage) => <li key={stage.id} className={stage.id === selectedStageId ? "is-selected" : ""}><button type="button" className="openmaic-stage-select" onClick={() => { setSelectedStageId(stage.id); setPlaying(false); }}><span className="row-copy"><strong>{stage.title}</strong><small>DSL {stage.dslVersion || "—"} · revision {stage.revision}</small></span><Icon name="PhCaretRight" size={15} /></button></li>)}</ol> : <div className="openmaic-home__empty"><Icon name="PhLayout" size={24} /><p>还没有内容</p><small>在上方输入主题，创建第一份学习内容。</small></div>}</Panel><div className="openmaic-workspace-page__content">{selectedStage ? <Panel><SectionHeading title={selectedStage.title} detail={`最近更新于 ${dateText(selectedStage.updatedAt)}`} action={<div className="openmaic-stage-heading-actions"><StageExportActions courseId={courseId} workspaceId={workspaceId} stage={selectedStage} canExportPptx={describeFusionState(fusionStatus).canExportPptx} /><Button variant="secondary" onClick={() => setPlaying((value) => !value)}>{playing ? "关闭播放" : "播放"}</Button></div>} />{playing ? <StagePlayerPanel courseId={courseId} workspaceId={workspaceId} stageId={selectedStage.id} onClose={() => setPlaying(false)} /> : <StageEditorPanel courseId={courseId} workspaceId={workspaceId} stageId={selectedStage.id} onSaved={load} />}</Panel> : <Panel><div className="openmaic-home__empty"><p>选择一个场景开始编辑。</p></div></Panel>}</div></div>
      <ProviderToolsPanel
        courseId={courseId}
        canTts={providerStatus?.state === "ready" && providerStatus.providers?.tts === true}
        canDiscussion={providerStatus?.state === "ready" && providerStatus.providers?.llm === true}
      />
      <p className="muted-copy">workspace revision {workspace?.revision || "—"} · <Link to={`/courses/${courseId}`}>返回课程详情</Link></p>
    </div></AsyncState>
  </PageFrame>;
}
