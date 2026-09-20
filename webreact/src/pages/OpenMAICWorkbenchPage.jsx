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
  NARROW_PANES,
  resolveStageChromeMode,
  resolveWorkbenchLayout,
  useNarrowViewport,
  useResizableWidth,
} from "../features/openmaic/workbenchLayoutModel.js";
import { resolveGenerationPhase } from "../features/openmaic/enterClassroomModel.js";

const MODES = [["slide", "幻灯片"], ["quiz", "测验"], ["interactive", "互动课堂"], ["pbl", "项目式学习"], ["simulation", "模拟"]];

/**
 * 窄屏面板切换器的文案。
 *
 * 和 `NARROW_PANES` 一一对应：渲染用的列表由模型导出，**没有**第二个"这里也写一遍"
 * 的地方，所以切换器不可能给出一个渲染不出来的面板，也不可能漏掉一个能渲染的面板。
 * 按钮的尺寸由各自的类决定（切换器要小，导航区要给「开始学习」和课程标签留位置），
 * 但可访问名称始终是这三个词。
 */
const NARROW_PANE_LABELS = { rail: "目录", classroom: "课堂", tools: "工具" };

/**
 * 窄屏工作台导航区：面板切换器 + 课程标签 + 出口。
 *
 * 语义上刻意**不使用** tab/tablist：
 *
 * - 一个 `tablist` 不能嵌在另一个 `tablist` 里，而这里的 `WorkspaceCourseTabs`
 *   自己就是一个合法的 tablist（它有真实的 tab 键盘契约）。把外层也标成 tablist
 *   会产出嵌套 tablist，屏幕阅读器读出来的层级是错的。
 * - 面板切换器又不是 `tabpanel` 的主人：三个面板是**互斥挂载**的，切换它们等于换
 *   视图，而不是在同一个 tabpanel 容器里换内容。半套 tab 语义（有 role="tab" 却
 *   没有 tabpanel、没有 roving tabindex 的完整键盘契约）比不用语义更糟。
 *
 * 所以外层是一个普通 `<nav>`，三个切换控件是普通 button + `aria-pressed`——这正是
 * "一组互斥的视图开关"的准确表达。键盘上按工具栏的惯例给它们 roving focus：
 * 方向键 / Home / End 移动并选中，Tab 只落在当前选中的那个上。
 */
function NarrowWorkbenchNav({ pane, onSelect, tabs, workspaceId, courseId, navigate, onCloseTab }) {
  const buttonsRef = useRef([]);

  const onSwitcherKeyDown = (event) => {
    const index = NARROW_PANES.indexOf(pane);
    if (index < 0) return;
    let next = null;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") next = (index + 1) % NARROW_PANES.length;
    else if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = (index - 1 + NARROW_PANES.length) % NARROW_PANES.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = NARROW_PANES.length - 1;
    if (next === null) return;
    event.preventDefault();
    // 先选中再聚焦：选中会重排（面板整个换掉），焦点要在新布局落定后仍然停在
    // 同一个控件上，所以顺序是"改状态 → 下一个微任务再聚焦"。
    onSelect(NARROW_PANES[next]);
    const target = buttonsRef.current[next];
    if (target) window.requestAnimationFrame(() => target.focus());
  };

  return <nav className="ow-nav" aria-label="工作台导航">
    <div
      className="ow-seg ow-seg--nav"
      role="group"
      aria-label="切换工作台面板"
      onKeyDown={onSwitcherKeyDown}
    >
      {NARROW_PANES.map((key, index) => <button
        key={key}
        ref={(node) => { buttonsRef.current[index] = node; }}
        type="button"
        // `aria-pressed` 而不是 `aria-selected`：这是一组互斥的视图开关。
        aria-pressed={pane === key}
        // roving focus：Tab 只停当前选中的那个，方向键在组内移动。
        tabIndex={pane === key ? 0 : -1}
        className={pane === key ? "is-active" : ""}
        onClick={() => onSelect(key)}
      >{NARROW_PANE_LABELS[key]}</button>)}
    </div>
    <WorkspaceCourseTabs
      tabs={tabs}
      activeCourseId={workspaceId}
      onActivate={(id) => { if (id !== workspaceId) navigate(`/courses/${courseId}/workspaces/${id}`); }}
      onClose={onCloseTab}
    />
    <button type="button" className="ow-icon-btn" aria-label="返回课程列表" title="返回课程列表" onClick={() => navigate("/courses")}>
      <Icon name="PhArrowLeft" size={15} />
    </button>
  </nav>;
}

const RAIL_STORAGE_KEY = "campus_openmaic_workbench_rail_width";
const RAIL_WIDTH_DEFAULT = 264;
const RAIL_WIDTH_MIN = 200;
const RAIL_WIDTH_MAX = 360;
const dateText = (value) => formatDateTime(value, { dateStyle: "medium", timeStyle: "short" }, "时间待定");
const errorText = (error, fallback = "工作台加载失败，请重试") => error?.response?.data?.detail || error?.response?.data?.message || error?.message || fallback;

/**
 * 量出工作台顶边到视口顶边的距离，写进 `--ow-top-offset`。
 *
 * 工作台是"撑满剩余高度"的三栏布局，高度必须等于「视口底边 - 工作台顶边」。它上面
 * 还有一条固定顶栏，而顶栏高度是随断点变的（手机 76px、桌面 88px…），所以写死任何
 * 一个数字都会在别的断点把面板底部切到屏幕外——实测 320×720 的「生成」和 1440×900
 * 的「生成」就是这样被裁掉、点不到的。这里直接量，不猜。
 */
function useTopOffset(ref) {
  const [offset, setOffset] = useState(0);
  useEffect(() => {
    const node = ref.current;
    if (!node || typeof ResizeObserver === "undefined") return undefined;
    const measure = () => {
      const top = Math.max(0, Math.round(node.getBoundingClientRect().top));
      setOffset((current) => (current === top ? current : top));
    };
    measure();
    const observer = new ResizeObserver(measure);
    // 观察工作台自己和它的父级：顶栏收起/展开、路由内容区高度变化都要重新量。
    observer.observe(node);
    if (node.parentElement) observer.observe(node.parentElement);
    window.addEventListener("resize", measure);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [ref]);
  return offset;
}

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
 * 1023px 及以下走**互斥单面板**——三栏并排会把 16:9 舞台压到无法使用（见
 * `resolveWorkbenchLayout`），此时用面板开关切换，而不是硬挤。
 *
 * 三件事刻意沿用参考项目的结论：
 *
 * - **编辑/播放不是开关，是推导。** 面板里的课堂是"编辑锁定"的，进播放的唯一门是
 *   「开始学习」。任何"编辑还没就绪"的中间态都落在 `loading` 上，不会闪一屏播放
 *   chrome 再跳回来。
 * - **切换编辑/播放不卸载编辑器。** 参考项目里两者是互斥挂载的，结果是切一次就
 *   丢掉编辑器状态；这里用 `hidden` 保留编辑器，只切换可见性。
 * - **面板的"在不在场"就是它的 `flex` 子项在不在。** 窄屏未激活的面板不进 DOM，
 *   而不是 `display: none`：后者仍然保留可聚焦元素，也仍然要跑自己的数据加载。
 *
 * ── 窄屏的工作台导航区（`ow-nav`）─────────────────────────────────────────
 *
 * 切换器**不**放在课堂面板头里。课堂是三者之一，把它当成另外两个的宿主，就会出现
 * "切到目录以后课堂连同切换器一起消失，再也回不去"的死角——而这正是本次要修的
 * 缺陷形态。所以切换器属于工作台本身，和课程标签、返回出口一起构成窄屏唯一持久的
 * 导航区，任何面板被选中时它都在。
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
  const rootRef = useRef(null);
  const narrow = useNarrowViewport();
  const topOffset = useTopOffset(rootRef);
  const rail = useResizableWidth({
    initial: RAIL_WIDTH_DEFAULT, min: RAIL_WIDTH_MIN, max: RAIL_WIDTH_MAX, storageKey: RAIL_STORAGE_KEY,
  });

  /**
   * 关掉一个已打开的课堂标签。
   *
   * `setTabsOpen` 的 updater **必须是纯函数**：React 允许重放它（StrictMode 下会
   * 故意跑两遍来暴露副作用，并发渲染也可能重放）。此前 `navigate()` 写在 updater
   * 内部，重放时就会导航两次——用户看不出差别，但后退栈会多出一格。
   *
   * 所以顺序是：先在事件回调里基于当前 `tabsOpen` 算出 `rest`，再
   * `setTabsOpen(rest)`，最后才在 updater **之外**导航。
   */
  const closeTab = useCallback((id) => {
    const rest = tabsOpen.filter((tab) => tab.id !== id);
    setTabsOpen(rest);
    // 关掉的不是当前课堂时不用跳；否则回退到剩下的最后一个标签。
    if (id === workspaceId) navigate(rest.length ? `/courses/${courseId}/workspaces/${rest[rest.length - 1].id}` : "/courses");
  }, [courseId, navigate, tabsOpen, workspaceId]);

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

  return <main
    className="ow-root"
    ref={rootRef}
    style={{ "--ow-top-offset": `${topOffset}px` }}
    data-testid="openmaic-workbench"
    data-ow-layout={layout.narrow ? "narrow" : "wide"}
    data-ow-pane={layout.pane}
  >
    {/* ── 窄屏唯一的持久导航区：面板切换器 + 课程标签 + 返回出口 ─────────────
        它渲染在**工作台**上，不属于任何一个面板，所以无论当前是目录、课堂还是
        工具，它都在。放进课堂面板头里会出现"切到目录就再也回不到课堂"的死角。 */}
    {layout.narrow ? <NarrowWorkbenchNav
      pane={layout.pane}
      onSelect={setNarrowPane}
      tabs={tabsOpen}
      workspaceId={workspaceId}
      courseId={courseId}
      navigate={navigate}
      onCloseTab={closeTab}
    /> : null}

    {/* ── 左栏：目录（窄屏下只有被选中时才存在） ───────────────────────── */}
    {layout.rail ? <aside
      className={`ow-pane ow-pane--rail${layout.railMini ? " is-mini" : ""}`}
      style={layout.railMini ? undefined : { width: layout.narrow ? undefined : rail.width }}
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
      {/* 生成入口：窄屏也必须有，否则"目录"面板里没有任何生成新内容的入口。 */}
      {!layout.railMini ? <div className="ow-composer">
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
      {/* 拖拽调宽只在宽屏、且 rail 不是 mini 时有意义。 */}
      {!layout.railMini && !layout.narrow ? resizeHandle : null}
    </aside> : null}

    {/* ── 中栏：课堂 ─────────────────────────────────────────────────── */}
    {layout.classroom ? <section className="ow-pane ow-pane--classroom" aria-label="课堂">
      <header className="ow-pane-head ow-classroom-head">
        {/* 宽屏：课程标签 + 导出 + 「开始学习」。窄屏这三样分别在导航区、舞台头
            和课程标签里，所以这里只保留「开始学习」这一个唯一的播放入口。 */}
        {layout.narrow ? null : <WorkspaceCourseTabs
          tabs={tabsOpen}
          activeCourseId={workspaceId}
          onActivate={(id) => { if (id !== workspaceId) navigate(`/courses/${courseId}/workspaces/${id}`); }}
          onClose={closeTab}
        />}
        {layout.narrow ? null : <span className="ow-ctabs-rule" aria-hidden="true" />}
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
            <small>在「目录」里输入主题，生成第一份内容。</small>
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
    </section> : null}

    {/* ── 右栏：课堂工具区（窄屏下只有被选中时才存在） ─────────────────── */}
    {layout.tools ? <aside className="ow-pane ow-pane--tools" aria-label="课堂工具">
      <header className="ow-pane-head">
        <span className="ow-pane-eyebrow">课堂工具</span>
        {/* "收起"是宽屏并排时的动作。窄屏工具是三个互斥面板之一，收起它等于把
            用户丢到一个没有面板的空白工作台上——退出这一栏的入口是导航区。 */}
        {layout.narrow ? null : <button type="button" className="ow-icon-btn" aria-label="收起课堂工具" title="收起课堂工具" onClick={() => setToolsCollapsed(true)}>
          <Icon name="PhCaretRight" size={15} />
        </button>}
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
