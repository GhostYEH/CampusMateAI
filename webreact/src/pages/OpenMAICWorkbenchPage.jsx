import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import * as api from "../data/api.js";
import { Button } from "../components/Primitives.jsx";
import { Icon } from "../components/Icon.jsx";
import StageEditorPanel from "../components/openmaic/StageEditorPanel.jsx";
import StagePlayerPanel from "../components/openmaic/StagePlayerPanel.jsx";
import ProviderToolsPanel from "../components/openmaic/ProviderToolsPanel.jsx";
import ContainBox from "../components/openmaic/ContainBox.jsx";
import ResizeHandle from "../components/openmaic/ResizeHandle.jsx";
import WorkspaceCourseTabs from "../components/openmaic/WorkspaceCourseTabs.jsx";
import WorkspaceSceneRail from "../components/openmaic/WorkspaceSceneRail.jsx";
import { normalizeStageList, normalizeWorkspaceList } from "../features/openmaic/workspaceModel.js";
import { describeFusionState } from "../features/openmaic/homeModel.js";
import { filenameFromContentDisposition } from "../features/openmaic/archiveModel.js";
import { formatDateTime } from "../utils/date.js";
import {
  resolveStageChromeMode,
  resolveWorkbenchLayout,
  useNarrowViewport,
  useResizableWidth,
} from "../features/openmaic/workbenchLayoutModel.js";
import { resolveGenerationPhase } from "../features/openmaic/enterClassroomModel.js";

const MODES = [["slide", "幻灯片"], ["quiz", "测验"], ["interactive", "互动课堂"], ["pbl", "项目式学习"], ["simulation", "模拟"]];
const RAIL_STORAGE_KEY = "campus_openmaic_workbench_rail_width";
const RAIL_WIDTH_DEFAULT = 264;
const RAIL_WIDTH_MIN = 200;
const RAIL_WIDTH_MAX = 360;
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
  // Chrome 是异步开始下载的，同一任务里就 revoke 会把有效下载取消掉。
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** 导出入口。只在服务端上报 export 能力时出现，绝不渲染一个必然失败的死按钮。 */
function ExportMenu({ courseId, workspaceId, stage, canExportPptx, canExportMarkdown, canExportDocx }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!stage) return null;

  async function run(format, suffix) {
    if (busy) return;
    setBusy(true); setError("");
    try {
      const result = await api.exportOpenMAICStageFormat(courseId, workspaceId, stage.id, format);
      saveBlob(result.blob, filenameFromContentDisposition(result.disposition) || `${stage.title}.${suffix}`);
      setOpen(false);
    } catch (failure) {
      setError(errorText(failure, "导出失败，请稍后重试"));
    } finally { setBusy(false); }
  }

  return <div className="ow-export">
    <Button variant="secondary" icon="PhDownloadSimple" aria-haspopup="true" aria-expanded={open} disabled={busy} onClick={() => setOpen((value) => !value)}>
      {busy ? "导出中…" : "导出"}
    </Button>
    {open ? <div className="ow-export__menu" role="menu">
      {canExportPptx ? <button type="button" role="menuitem" disabled={busy} onClick={() => run("pptx", "pptx")}>导出 PPTX</button> : null}
      {canExportMarkdown ? <button type="button" role="menuitem" disabled={busy} onClick={() => run("markdown", "md")}>导出 Markdown</button> : null}
      {canExportDocx ? <button type="button" role="menuitem" disabled={busy} onClick={() => run("docx", "docx")}>导出 DOCX</button> : null}
      {!canExportPptx && !canExportMarkdown && !canExportDocx ? <span className="ow-export__empty">本部署未启用导出</span> : null}
    </div> : null}
    {error ? <span className="ow-hint ow-hint--error" role="alert">{error}</span> : null}
  </div>;
}

/**
 * 学习工作台。
 *
 * 三栏：左（课程/场景目录 + 可打开的课堂标签）、中（16:9 舞台）、右（课堂工具）。
 * 768–1023px 走**互斥单面板**——三栏并排会把 16:9 舞台压到无法使用（见
 * `resolveWorkbenchLayout`），此时用面板开关切换，而不是硬挤。
 *
 * 两件事刻意沿用参考项目的结论：
 *
 * - **编辑/播放不是开关，是推导。** 面板里的课堂是"编辑锁定"的，进播放的唯一门是
 *   「开始学习」。任何"编辑还没就绪"的中间态都落在 `loading` 上，不会闪一屏播放
 *   chrome 再跳回来。
 * - **切换编辑/播放不卸载编辑器。** 参考项目里两者是互斥挂载的，结果是切一次就
 *   丢掉编辑器状态；这里用 `hidden` 保留编辑器，只切换可见性。
 */
export default function OpenMAICWorkbenchPage() {
  const { courseId, workspaceId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const launchPrompt = searchParams.get("prompt")?.trim() || "";

  const [workspace, setWorkspace] = useState(null);
  const [stages, setStages] = useState([]);
  const [selectedStageId, setSelectedStageId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [providerStatus, setProviderStatus] = useState(null);
  const [fusionStatus, setFusionStatus] = useState(null);
  const [mode, setMode] = useState("slide");
  const [prompt, setPrompt] = useState("");
  const [job, setJob] = useState(null);
  const [busy, setBusy] = useState(false);
  // 播放是**推导出来的**一个输入：只有用户按「开始学习」它为真。
  const [learning, setLearning] = useState(false);
  const [toolsCollapsed, setToolsCollapsed] = useState(false);
  const [narrowPane, setNarrowPane] = useState("classroom");
  const [tabsOpen, setTabsOpen] = useState([]);

  const epoch = useRef(0);
  const polling = useRef(null);
  const launchStarted = useRef(false);
  const narrow = useNarrowViewport();
  const rail = useResizableWidth({
    initial: RAIL_WIDTH_DEFAULT, min: RAIL_WIDTH_MIN, max: RAIL_WIDTH_MAX, storageKey: RAIL_STORAGE_KEY,
  });

  const load = useCallback(async () => {
    const mine = ++epoch.current;
    setLoading(true); setError("");
    try {
      const [workspacePayload, stagePayload] = await Promise.all([
        api.getOpenMAICWorkspace(courseId, workspaceId),
        api.listOpenMAICStages(courseId, workspaceId, { limit: 50 }),
      ]);
      if (mine !== epoch.current) return;
      const nextWorkspace = normalizeWorkspaceList({ items: [workspacePayload] })[0] || null;
      const nextStages = normalizeStageList(stagePayload);
      setWorkspace(nextWorkspace);
      setStages(nextStages);
      setSelectedStageId((current) => (nextStages.some((stage) => stage.id === current) ? current : nextStages[0]?.id || ""));
    } catch (failure) {
      if (mine !== epoch.current) return;
      setWorkspace(null); setStages([]); setError(errorText(failure));
    } finally {
      if (mine === epoch.current) setLoading(false);
    }
  }, [courseId, workspaceId]);

  useEffect(() => {
    setJob(null); setLearning(false);
    void load();
    // 能力状态各自独立降级：取不到时只是入口关闭，不影响已有内容。
    api.getOpenMAICProviderStatus().then(setProviderStatus).catch(() => setProviderStatus(null));
    api.getOpenMAICFusionStatus().then(setFusionStatus).catch(() => setFusionStatus(null));
    return () => { if (polling.current) window.clearTimeout(polling.current); };
  }, [load]);

  // 打开的课堂标签。当前 workspace 始终在列表里，且是活动项。
  useEffect(() => {
    if (!workspace?.id) return;
    setTabsOpen((current) => (current.some((tab) => tab.id === workspace.id)
      ? current
      : [...current, { id: workspace.id, name: workspace.name }]));
  }, [workspace]);

  const pollJob = useCallback(async (jobId) => {
    const mine = epoch.current;
    try {
      const current = await api.getOpenMAICJob(courseId, jobId);
      if (mine !== epoch.current) return;
      setJob(current);
      if (["queued", "running"].includes(current.status)) {
        polling.current = window.setTimeout(() => void pollJob(jobId), 800);
      } else if (current.status === "completed") {
        setNotice("学习内容已生成，并已写入当前工作台。");
        await load();
      }
    } catch (failure) {
      if (mine !== epoch.current) return;
      setError(errorText(failure, "生成进度读取失败"));
    }
  }, [courseId, load]);

  const generatePrompt = useCallback(async (value) => {
    const normalized = String(value || "").trim();
    if (!normalized || busy) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await api.generateOpenMAICStage(courseId, workspaceId, {
        mode, prompt: normalized, idempotencyKey: api.newIdempotencyKey(),
      });
      setJob(result.job || null);
      setPrompt("");
      await load();
      if (result.job?.id && result.job.status !== "completed") void pollJob(result.job.id);
      else setNotice("学习内容已生成，并已写入当前工作台。");
    } catch (failure) {
      setError(errorText(failure, "生成失败，原工作台内容未改变"));
    } finally { setBusy(false); }
  }, [busy, courseId, load, mode, pollJob, workspaceId]);

  // 由「进入课堂」带 prompt 跳进来时自动生成首个内容；已有 stage 则只恢复。
  useEffect(() => {
    if (loading || !workspace || !launchPrompt || stages.length > 0 || launchStarted.current) return;
    launchStarted.current = true;
    setPrompt(launchPrompt);
    void generatePrompt(launchPrompt);
  }, [loading, workspace, stages.length, launchPrompt, generatePrompt]);

  async function cancelJob() {
    if (!job?.id) return;
    setBusy(true);
    try { setJob(await api.cancelOpenMAICJob(courseId, job.id)); setNotice("已请求中断生成。"); }
    catch (failure) { setError(errorText(failure, "中断失败")); }
    finally { setBusy(false); }
  }
  async function retryJob() {
    if (!job?.id) return;
    setBusy(true);
    try { const next = await api.retryOpenMAICJob(courseId, job.id); setJob(next); void pollJob(next.id); }
    catch (failure) { setError(errorText(failure, "重试失败")); }
    finally { setBusy(false); }
  }

  const selectedStage = useMemo(() => stages.find((stage) => stage.id === selectedStageId) || null, [stages, selectedStageId]);
  const jobPhase = job ? resolveGenerationPhase(job) : null;
  const jobBusy = Boolean(job && ["queued", "running"].includes(job.status));
  const fusion = describeFusionState(fusionStatus);
  const layout = resolveWorkbenchLayout({
    narrow, activePane: narrowPane, classroomOpen: true, toolsCollapsed,
  });

  // 模式是推导的：进播放只有「开始学习」一条路。
  const chromeMode = resolveStageChromeMode({
    hosted: true,
    workbenchLearning: learning,
    workbenchShowingClassroom: true,
    isEditable: Boolean(selectedStage),
    hasCurrentScene: Boolean(selectedStage),
  });

  const resizeHandle = <ResizeHandle
    label="拖动调整目录宽度"
    value={rail.width}
    min={RAIL_WIDTH_MIN}
    max={RAIL_WIDTH_MAX}
    onCommit={rail.commit}
    onReset={rail.reset}
  />;

  return <main className="ow-root" data-testid="openmaic-workbench" data-ow-layout={layout.narrow ? "narrow" : "wide"}>
    {/* ── 左下 / 左栏：目录 ───────────────────────────────────────────── */}
    {layout.rail ? <aside
      className={`ow-pane ow-pane--rail${layout.railMini ? " is-mini" : ""}`}
      style={layout.railMini ? undefined : { width: rail.width }}
      aria-label="课堂目录"
    >
      <header className="ow-pane-head">
        <span className="ow-pane-eyebrow">OpenMAIC</span>
        <span className="ow-pane-title" title={workspace?.name || "学习工作台"}>{workspace?.name || "学习工作台"}</span>
        <button type="button" className="ow-icon-btn" aria-label="返回课程列表" title="返回课程列表" onClick={() => navigate("/courses")}>
          <Icon name="PhArrowLeft" size={15} />
        </button>
      </header>
      <div className="ow-pane-body">
        <WorkspaceSceneRail
          stages={stages}
          selectedStageId={selectedStageId}
          onSelect={(id) => { setSelectedStageId(id); setLearning(false); setNarrowPane("classroom"); }}
          generating={jobBusy}
          progress={jobPhase?.percent || 0}
          failure={job?.status === "failed" ? (job.error || job.error_code || "受管服务未给出具体原因") : null}
          onRetry={retryJob}
          loading={loading}
          className={layout.railMini ? "is-hidden" : ""}
        />
      </div>
      {/* 生成入口只在宽屏出现；窄屏空间要留给舞台。 */}
      {!layout.railMini && !narrow ? <div className="ow-composer">
        <form onSubmit={(event) => { event.preventDefault(); void generatePrompt(prompt); }}>
          <label className="ow-composer__field">
            <span className="ow-sr-only">学习内容主题</span>
            <input
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="继续生成新的课堂内容…"
              maxLength={2000}
              aria-label="学习内容主题"
            />
          </label>
          <select value={mode} onChange={(event) => setMode(event.target.value)} aria-label="学习内容类型">
            {MODES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <Button type="submit" disabled={busy || !prompt.trim()}>{busy ? "提交中…" : "生成"}</Button>
        </form>
      </div> : null}
      {/* 宽屏下用拖拽手柄调宽；窄屏 rail 是 mini，不提供拖拽。 */}
      {!layout.railMini ? resizeHandle : null}
    </aside> : null}

    {/* ── 中栏 + 右栏：课堂与工具 ─────────────────────────────────────── */}
    <section className="ow-pane ow-pane--classroom" aria-label="课堂">
      <header className="ow-pane-head ow-classroom-head">
        {/* 折叠/展开在窄屏是面板开关；宽屏是工具区开关。 */}
        {layout.narrow ? <div className="ow-seg" role="tablist" aria-label="面板切换">
          {[["rail", "目录"], ["classroom", "课堂"], ["tools", "工具"]].map(([key, label]) => <button
            key={key}
            type="button"
            role="tab"
            aria-selected={narrowPane === key}
            tabIndex={narrowPane === key ? 0 : -1}
            className={narrowPane === key ? "is-active" : ""}
            onClick={() => setNarrowPane(key)}
          >{label}</button>)}
        </div> : null}
        <WorkspaceCourseTabs
          tabs={tabsOpen}
          activeCourseId={workspaceId}
          onActivate={(id) => { if (id !== workspaceId) navigate(`/courses/${courseId}/workspaces/${id}`); }}
          onClose={(id) => {
            const rest = tabsOpen.filter((tab) => tab.id !== id);
            setTabsOpen(rest);
            if (id === workspaceId) navigate(rest.length ? `/courses/${courseId}/workspaces/${rest[rest.length - 1].id}` : "/courses");
          }}
        />
        <span className="ow-ctabs-rule" aria-hidden="true" />
        <ExportMenu
          courseId={courseId}
          workspaceId={workspaceId}
          stage={selectedStage}
          canExportPptx={fusion.canExportPptx}
          canExportMarkdown={fusion.canExportMarkdown}
          canExportDocx={fusion.canExportDocx}
        />
        {/* 「开始学习」是进入播放的唯一门。 */}
        <button
          type="button"
          className="ow-start"
          data-testid="ow-start-learning"
          disabled={!selectedStage}
          aria-pressed={learning}
          onClick={() => { setLearning((value) => !value); setNarrowPane("classroom"); }}
        >
          <Icon name={learning ? "PhPencilSimple" : "PhPlay"} size={14} />
          {learning ? "返回编辑" : "开始学习"}
        </button>
      </header>

      <div className="ow-classroom-body">
        {/* 生成中进行中：真实进度，真实阶段文案。 */}
        {jobBusy || job?.status === "failed" ? <div className={`ow-progress${job?.status === "failed" ? " is-failed" : ""}`} role="status">
          <div className="ow-progress__copy">
            <strong>{jobPhase?.title || "生成中"}</strong>
            <small>{job?.status === "failed" ? (job.error || job.error_code || "生成失败") : (jobPhase?.description || "正在生成课堂内容…")}</small>
          </div>
          <div className="ow-progress__bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={jobPhase?.percent || 0}>
            <span style={{ width: `${jobPhase?.percent || 0}%` }} />
          </div>
          <div className="ow-progress__actions">
            {jobBusy ? <Button variant="quiet" disabled={busy} onClick={cancelJob}>中断</Button> : null}
            {job?.status === "failed" ? <Button variant="secondary" disabled={busy} onClick={retryJob}>重试生成</Button> : null}
          </div>
        </div> : null}

        {error ? <div className="ow-inline-error" role="alert">
          <Icon name="PhWarningCircle" size={18} />
          <div><strong>{error}</strong><small>工作台其余部分不受影响，可重试或继续使用已有内容。</small></div>
          <Button variant="secondary" onClick={load} disabled={loading}>重新读取</Button>
        </div> : null}

        {notice ? <p className="ow-hint" role="status">{notice}</p> : null}

        {loading ? <div className="ow-stage-state" aria-busy="true"><span className="loading-orb" /><p>正在打开工作台…</p></div>
          : !selectedStage ? <div className="ow-stage-state">
            <Icon name="PhLayout" size={30} />
            <p>这个工作台还没有课堂内容</p>
            <small>{narrow ? "在「目录」里生成新的内容。" : "在左下输入主题，生成第一份内容。"}</small>
          </div>
          : <>
            {/* 播放态与编辑态**同时挂载**，用可见性切换：切一次不会丢编辑器状态。 */}
            <div className={`ow-stage${chromeMode === "playback" ? " is-playback" : ""}`}>
              <ContainBox label="课堂舞台">
                <div className="ow-stage__inner">
                  {chromeMode === "playback"
                    ? <StagePlayerPanel courseId={courseId} workspaceId={workspaceId} stageId={selectedStage.id} onClose={() => setLearning(false)} />
                    : <StageEditorPanel courseId={courseId} workspaceId={workspaceId} stageId={selectedStage.id} onSaved={load} />}
                </div>
              </ContainBox>
            </div>
            <p className="ow-stage-meta">
              最近更新于 {dateText(selectedStage.updatedAt)} · workspace revision {workspace?.revision || "—"} ·{" "}
              <Link to={`/courses/${courseId}`}>返回课程详情</Link>
            </p>
          </>}
      </div>
    </section>

    {/* ── 右栏：课堂工具区 ─────────────────────────────────────────────── */}
    {layout.tools && !layout.narrow ? <aside className="ow-pane ow-pane--tools" aria-label="课堂工具">
      <header className="ow-pane-head">
        <span className="ow-pane-eyebrow">课堂工具</span>
        <button type="button" className="ow-icon-btn" aria-label="收起课堂工具" title="收起课堂工具" onClick={() => setToolsCollapsed(true)}>
          <Icon name="PhCaretRight" size={15} />
        </button>
      </header>
      <div className="ow-pane-body">
        <ProviderToolsPanel
          courseId={courseId}
          canTts={providerStatus?.state === "ready" && providerStatus.providers?.tts === true}
          canDiscussion={providerStatus?.state === "ready" && providerStatus.providers?.llm === true}
        />
      </div>
    </aside> : null}

    {!layout.tools && !layout.narrow ? <button type="button" className="ow-tools-reopen" aria-label="展开课堂工具" onClick={() => setToolsCollapsed(false)}>
      <Icon name="PhCaretLeft" size={14} /><span>课堂工具</span>
    </button> : null}
  </main>;
}
