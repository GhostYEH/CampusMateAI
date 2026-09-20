import React from "react";
import { ChevronLeft, ChevronRight, LayoutList, Pause, Play } from "lucide-react";
import { Button } from "../Primitives.jsx";
import { Icon } from "../Icon.jsx";
import * as api from "../../data/api.js";
import { MaicClassroomShell } from "../../maic/classroom/index.js";
import { ctrlBtn } from "../../maic/classroom/classroom-header.jsx";
import { MaicSceneRenderer } from "../../maic/scene/index.js";
import { MaicSlideSurface } from "../../maic/slide/index.js";
import { MaicRoundtable } from "../../maic/roundtable/index.jsx";
import SimulationRuntimePanel from "./SimulationRuntimePanel.jsx";
import { cn } from "../../maic/utils/cn.js";
import {
  degradeNotice,
  describePlaybackError,
  normalizePlayback,
  sandboxPolicyFor,
} from "../../features/openmaic/playerModel.js";
import {
  describeDiscussionFailure,
  discussionPromptFor,
  discussionRejection,
  normalizeDiscussionMessages,
} from "../../features/openmaic/roundtableModel.js";
import { SCENE_TYPE_LABELS } from "../../features/openmaic/editorModel.js";
import { useNarrowViewport } from "../../features/openmaic/workbenchLayoutModel.js";
import { useSceneNarration } from "../../features/openmaic/useSceneNarration.js";
import { canGenerateNarration, narrationLabel } from "../../features/openmaic/narrationModel.js";
import {
  advanceActionTimeline,
  isPlaybackShortcutTarget,
  startActionTimeline,
} from "../../features/openmaic/playbackTimeline.js";
import { useCanvasStore } from "../../maic/slide/index.js";

/**
 * 学习态课堂：把参考项目（清华大学学习平台 / OpenMAIC）的播放态界面接到
 * CampusMate 的真实数据上。
 *
 * 四类事实在这里汇合，混任何一类都会退化成"看起来像课堂"：
 *
 * 1. **渲染决定由服务端给。** 场景列表取自播放计划（`render.kind` 是服务端的
 *    判断）；正文取自授权的单场景端点。前端不自己猜"这个场景大概能渲染"——
 *    猜错的代价是把不该进 iframe 的内容放进去，或者用空白冒充"渲染中"。
 * 2. **沙箱只减不增。** 只有服务端标了 `sandbox-*` 且沙箱串不含
 *    `allow-same-origin` 才允许 iframe，判据复用 `sandboxPolicyFor`。
 * 3. **迟到的响应不得写进新上下文。** 换舞台用 epoch 挡，换场景用 cancelled 挡；
 *    缺任何一个，快速连点都会让旧响应覆盖新内容。
 * 4. **不编造内容。** 正文读不到就说读不到，只显示标题。
 *
 * 布局是**全出血**的：参考项目的全屏播放会把工作台让到一边
 * （"Full-screen playback steps the workspace aside"），所以左栏（场景列表）
 * 与头栏由课堂自己提供，不叠加工作台的三栏。
 */
export default function OpenMAICClassroomStage({
  courseId,
  workspaceId,
  stageId,
  fallbackTitle = "",
  onExit,
}) {
  const [plan, setPlan] = React.useState(null);
  // 场景正文按 id 索引。整份舞台文档一次取回（`GET .../stages/{id}` 返回
  // document.scenes），因此侧栏缩略图与主画布**共用同一次读取**——逐场景拉正文
  // 会让 8 个场景变成 8 次请求，而且侧栏缩略图根本拿不到内容，只能显示灰框。
  const [contentByScene, setContentByScene] = React.useState({});
  const [index, setIndex] = React.useState(0);
  // 侧栏默认宽度 220px。320px 视口下它会把主列压到 100px：头栏的返回按钮与右侧
  // 控制簇互相重叠，「返回编辑」点不到。所以窄屏（≤1023px）一进来就收起侧栏，
  // 但**跨断点时才重置**——用户在同一个断点里的手动开合不被覆盖。
  const narrow = useNarrowViewport();
  const [collapsed, setCollapsed] = React.useState(narrow);
  const wasNarrow = React.useRef(narrow);
  React.useEffect(() => {
    if (wasNarrow.current === narrow) return;
    wasNarrow.current = narrow;
    setCollapsed(narrow);
  }, [narrow]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");
  const [isPresenting, setIsPresenting] = React.useState(false);
  const epoch = React.useRef(0);

  React.useEffect(() => {
    if (!isPresenting) return undefined;
    const onKeyDown = (event) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      if (isPresenting) setIsPresenting(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isPresenting]);

  const load = React.useCallback(async () => {
    const mine = (epoch.current += 1);
    setLoading(true);
    setError("");
    try {
      // 播放计划给**渲染决定**（render.kind 是服务端的判断，前端不自己猜），
      // 舞台文档给**正文**。两者一起取，任一失败都算这次读取失败。
      const [playback, stageDocument] = await Promise.all([
        api.getOpenMAICStagePlayback(courseId, workspaceId, stageId),
        api.getOpenMAICStage(courseId, workspaceId, stageId),
      ]);
      if (mine !== epoch.current) return; // 迟到的响应不得写进新上下文
      const normalized = normalizePlayback(playback);
      setPlan(normalized);
      setIndex(normalized.startIndex);
      setContentByScene(indexScenesById(stageDocument));
    } catch (failure) {
      if (mine !== epoch.current) return;
      setPlan(null);
      setContentByScene({});
      setError(describePlaybackError(failure).message);
    } finally {
      if (mine === epoch.current) setLoading(false);
    }
  }, [courseId, workspaceId, stageId]);

  React.useEffect(() => {
    void load();
  }, [load]);

  // 换舞台必须归零：上一份正文留在屏幕上比空白更糟。
  React.useEffect(() => {
    setIndex(0);
    setContentByScene({});
  }, [courseId, workspaceId, stageId]);

  const scenes = plan?.scenes || [];
  const current = scenes[index] || null;
  const currentId = current?.id || "";
  const scene = currentId ? contentByScene[currentId] || null : null;
  // 正文随舞台文档一次取回，所以**没有**逐场景的加载态：只有整体还在读时才转圈。
  // 写成 `Boolean(currentId) && scene === null` 会让"该场景不在文档里"永久转圈，
  // 那是把"读不到"伪装成"正在读"——必须落到下面那条如实的兜底文案。
  const sceneLoading = loading;

  // 侧栏要的是「导航信息 + 缩略图内容」：导航信息来自播放计划（顺序与渲染决定），
  // 缩略图内容来自舞台文档。把两者合到一份列表，`SceneThumbnailContent` 才能拿到
  // `scene.content`；只传播放计划的话 slide 缩略图永远是灰框。
  const sidebarScenes = React.useMemo(
    () => scenes.map((entry) => ({ ...entry, content: contentByScene[entry.id]?.content })),
    [scenes, contentByScene],
  );

  const go = React.useCallback((next) => {
    setIndex((currentIndex) => (next < 0 || next > scenes.length - 1 ? currentIndex : next));
  }, [scenes.length]);

  // 动作计划来自服务端、参数来自已授权的舞台文档；播放状态只属于当前场景。
  // 两者分开后，播放器不会为了猜一个 `elementId` 而把效果施加到错误的画布上。
  const [actionSession, setActionSession] = React.useState(null);
  const [playbackNotice, setPlaybackNotice] = React.useState("");
  const resetActionTimeline = React.useCallback(() => {
    useCanvasStore.resetEffects();
    useCanvasStore.pauseVideo();
    setActionSession(null);
    setPlaybackNotice("");
  }, []);

  React.useEffect(() => {
    resetActionTimeline();
    return () => {
      useCanvasStore.resetEffects();
      useCanvasStore.pauseVideo();
    };
  }, [currentId, resetActionTimeline]);

  const toggleActionTimeline = React.useCallback(() => {
    setActionSession((previous) => {
      if (previous?.status === "playing") return { ...previous, status: "paused", clearEffects: false };
      if (previous?.status === "paused") return { ...previous, status: "playing", clearEffects: false };
      const next = startActionTimeline(current, scene);
      useCanvasStore.resetEffects();
      useCanvasStore.pauseVideo();
      setPlaybackNotice(next.status === "completed" ? "这一页没有可执行的播放动作。" : "正在播放本页动作…");
      return next;
    });
  }, [current, scene]);

  React.useEffect(() => {
    if (!actionSession || actionSession.status !== "playing") return undefined;
    const timer = window.setTimeout(() => {
      const result = advanceActionTimeline(actionSession);
      if (result.effect) {
        if (result.effect.kind === "spotlight") useCanvasStore.setSpotlight(result.effect.elementId, result.effect.options);
        if (result.effect.kind === "laser") useCanvasStore.setLaser(result.effect.elementId, result.effect.options);
        if (result.effect.kind === "play_video") useCanvasStore.playVideo(result.effect.elementId);
      }
      if (result.skipped) {
        setPlaybackNotice(`动作「${result.skipped.type}」未执行：${result.skipped.reason === "element_not_found" ? "目标元素不存在" : "当前客户端没有对应运行时"}。`);
      } else if (result.next?.status === "completed") {
        setPlaybackNotice("本页动作已播放完成。");
      }
      setActionSession(result.next);
    }, 260);
    return () => window.clearTimeout(timer);
  }, [actionSession]);

  React.useEffect(() => {
    const onKeyDown = (event) => {
      if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
      if (isPlaybackShortcutTarget(event.target) || isPlaybackShortcutTarget(document.activeElement)) return;
      if (event.key === "ArrowLeft" && isPresenting) {
        event.preventDefault();
        go(index - 1);
      } else if (event.key === "ArrowRight" && isPresenting) {
        event.preventDefault();
        go(index + 1);
      } else if (event.key === " " || event.key === "Spacebar") {
        event.preventDefault();
        toggleActionTimeline();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [go, index, isPresenting, toggleActionTimeline]);

  // ── 讲解音频 ─────────────────────────────────────────────────────────────
  // 按**当前场景**取音频。hook 内部以 sceneId 为键并在换场景时释放 blob，
  // 所以 A 页的音频不可能出现在 B 页上；刷新后关联由服务端反查给出。
  const narration = useSceneNarration({ courseId, workspaceId, stageId, sceneId: currentId });

  // ── 圆桌讨论 ─────────────────────────────────────────────────────────────
  // 讨论是**任务式**的（提交 → 轮询 job → 取 artifact），不是流式。所以状态只有
  // 四态：空 / 进行中 / 有发言 / 失败。守卫与播放那套同源：换场景或重复提交时，
  // 在飞任务的结果不得写进新上下文。
  const [topic, setTopic] = React.useState("");
  const [discussing, setDiscussing] = React.useState(false);
  const [messages, setMessages] = React.useState([]);
  const [discussionError, setDiscussionError] = React.useState("");
  const discussionEpoch = React.useRef(0);

  // 主题默认跟随当前场景。只在**换场景**时重置——跟随每次渲染会把用户正在输入的
  // 内容冲掉。
  React.useEffect(() => {
    discussionEpoch.current += 1; // 作废在飞的讨论
    setTopic(discussionPromptFor(current?.title || ""));
    setMessages([]);
    setDiscussionError("");
    setDiscussing(false);
  }, [currentId]);

  const runDiscussion = React.useCallback(async () => {
    if (discussionRejection({ prompt: topic, busy: discussing })) return;
    const mine = (discussionEpoch.current += 1);
    setDiscussing(true);
    setDiscussionError("");
    setMessages([]);
    try {
      const started = await api.runOpenMAICDiscussion(courseId, {
        prompt: topic.trim(),
        idempotencyKey: api.newIdempotencyKey(),
      });
      // 服务端会**同时**回 `job_id` 与一个 `job` 快照（通常是 `queued`）。
      // 判据必须是"这个 job 还没完成就轮询"，而不是"没给 job 对象才轮询"——
      // 后者会拿到一个 queued 快照后径直按失败处理，表现为"提交了但永远没结果"。
      let job = started?.job ?? null;
      if (job?.status !== "completed" && started?.job_id) {
        job = await waitForDiscussionJob(courseId, started.job_id, () => mine === discussionEpoch.current);
      }
      if (mine !== discussionEpoch.current) return;
      if (!job) throw new Error("受管服务未返回任务编号");
      if (job.status !== "completed") throw new Error(job.error_code || "讨论任务未完成");

      const artifact = await api.getOpenMAICArtifact(courseId, job.artifact_id);
      const payload = JSON.parse(await artifact.blob.text());
      if (mine !== discussionEpoch.current) return;
      const normalized = normalizeDiscussionMessages(payload);
      setMessages(normalized);
      // "任务完成但没有发言"必须如实说，不能显示成一场已结束的讨论。
      if (!normalized.length) setDiscussionError("讨论任务完成了，但没有返回任何发言内容。");
    } catch (failure) {
      if (mine === discussionEpoch.current) setDiscussionError(describeDiscussionFailure(failure));
    } finally {
      if (mine === discussionEpoch.current) setDiscussing(false);
    }
  }, [courseId, topic, discussing]);

  if (loading) {
    return <div className="maic-root flex-1 flex items-center justify-center bg-gray-50" aria-busy="true">
      <div className="flex flex-col items-center gap-3 text-muted-foreground">
        <span className="loading-orb" />
        <p>{fallbackTitle || "正在打开课堂…"}</p>
      </div>
    </div>;
  }

  if (error) {
    return <div className="maic-root flex-1 flex items-center justify-center bg-gray-50" role="alert">
      <div className="flex flex-col items-center gap-3 text-center max-w-md px-6">
        <Icon name="PhWarningCircle" size={34} />
        <strong>{error}</strong>
        <p className="text-sm text-muted-foreground">课堂正文读不到时不用占位内容冒充，请稍后重试。</p>
        <div className="flex gap-2 mt-1">
          <Button type="button" variant="secondary" onClick={load}>重新读取</Button>
          {onExit ? <Button type="button" variant="quiet" onClick={onExit}>返回编辑</Button> : null}
        </div>
      </div>
    </div>;
  }

  if (!scenes.length) {
    return <div className="maic-root flex-1 flex items-center justify-center bg-gray-50">
      <div className="flex flex-col items-center gap-3 text-center max-w-md px-6">
        <Icon name="PhLayout" size={30} />
        <strong>这个课堂还没有内容</strong>
        <p className="text-sm text-muted-foreground">返回编辑，在「目录」里输入主题生成第一份学习内容。</p>
        {onExit ? <Button type="button" variant="secondary" onClick={onExit}>返回编辑</Button> : null}
      </div>
    </div>;
  }

  return <div
    className="maic-root flex-1 min-h-0 min-w-0 flex"
    data-presentation-mode={isPresenting ? "true" : "false"}
  >
    <MaicClassroomShell
      title={plan?.title || fallbackTitle}
      scenes={sidebarScenes}
      currentSceneId={currentId}
      onSelectScene={(id) => {
        const next = scenes.findIndex((entry) => entry.id === id);
        if (next >= 0) go(next);
      }}
      onPrevScene={index > 0 ? () => go(index - 1) : undefined}
      onNextScene={index < scenes.length - 1 ? () => go(index + 1) : undefined}
      sidebarCollapsed={collapsed}
      onToggleSidebar={() => setCollapsed((value) => !value)}
      isPresenting={isPresenting}
      onTogglePresentation={() => setIsPresenting((value) => !value)}
      // 参考项目侧栏顶部是 `<img src="/logo-horizontal.png">`。目标仓库没有这个
      // 品牌图，直接沿用会渲染成一张破图（alt 文本裸露、占据 h-6 高度）。把上游
      // 二进制搬进来要走 third_party 的 LICENSE/NOTICE/清单流程，不属于本次范围，
      // 所以用同槽位的文字字标替代：视觉角色一致（一行品牌标识），且不会破图。
      sidebarProps={{
        headerSlot: <span className="text-[15px] font-black tracking-tight text-gray-900 dark:text-gray-100">{"magic'class"}</span>,
        // 侧栏缩略图走**同一份**正文：有真实画布就画真实缩略图，没有就交给移植层
        // 自带的占位分支。参考项目这里用的是 `SlideThumbnail`，本仓库没有该组件，
        // 所以复用播放画布（`MaicSlideSurface`）在缩略图尺寸下渲染——缩略图与大图
        // 因此不可能不一致。
        renderSlideThumbnail: ({ slide, sceneId }) => (
          <SlideThumbnail canvas={slide} sceneId={sceneId} />
        ),
      }}
      backControl={onExit ? <Button
        type="button"
        variant="secondary"
        size="sm"
        data-testid="ow-classroom-back"
        onClick={onExit}
      >
        <Icon name="PhArrowLeft" size={14} />
        返回编辑
      </Button> : undefined}
      // 页码不放在头栏：参考项目的头栏没有页码，它在工具栏左侧（见 SceneToolbar）。
      // 两边各放一个会让同一件事出现两个数字。
    >
      <SceneStage
        scene={scene}
        outline={current}
        loading={sceneLoading}
        index={index}
        total={scenes.length}
        sidebarCollapsed={collapsed}
        onToggleSidebar={() => setCollapsed((value) => !value)}
        onPrev={index > 0 ? () => go(index - 1) : undefined}
        onNext={index < scenes.length - 1 ? () => go(index + 1) : undefined}
        topic={topic}
        onTopicChange={setTopic}
        onStartDiscussion={runDiscussion}
        discussing={discussing}
        messages={messages}
        discussionError={discussionError}
        narration={narration}
        isPresenting={isPresenting}
        actionSession={actionSession}
        playbackNotice={playbackNotice}
        onToggleActionTimeline={toggleActionTimeline}
      />
    </MaicClassroomShell>
  </div>;
}

/**
 * 画布区。只负责**如实执行**服务端给出的渲染决定：
 * 原生交给移植来的渲染器，沙箱交给最小 sandbox 的 iframe，其余说清缺什么。
 */
function SceneStage({
  scene,
  outline,
  loading,
  index,
  total,
  sidebarCollapsed,
  onToggleSidebar,
  onPrev,
  onNext,
  topic,
  onTopicChange,
  onStartDiscussion,
  discussing,
  messages,
  discussionError,
  narration,
  isPresenting,
  actionSession,
  playbackNotice,
  onToggleActionTimeline,
}) {
  const title = outline?.title || "";
  const type = outline?.type || "unknown";
  const policy = sandboxPolicyFor(outline?.render);

  const sandboxHtml = typeof scene?.content?.html === "string" ? scene.content.html : "";
  const sandboxUrl = typeof scene?.content?.url === "string" ? scene.content.url : "";
  const isNativeSimulation = scene?.content?.type === "interactive"
    && scene.content.widgetType === "simulation";

  let body;
  if (loading) {
    body = <div className="flex flex-col items-center gap-3 text-gray-400">
      <span className="loading-orb" />
      <p>正在读取场景内容…</p>
    </div>;
  } else if (isNativeSimulation) {
    body = <SimulationRuntimePanel content={scene.content} sceneId={scene.id} />;
  } else if (policy.allowIframe && (sandboxHtml || sandboxUrl)) {
    body = <iframe
      className="w-full h-full border-0 bg-white"
      title={title}
      sandbox={policy.sandbox}
      referrerPolicy="no-referrer"
      {...(outline?.render?.kind === "sandbox-html" ? { srcDoc: sandboxHtml } : { src: sandboxUrl })}
    />;
  } else if (policy.allowIframe) {
    body = <Fallback title={title} type={type} text="该互动场景没有可播放的内容，服务端标记为沙箱但未给出正文。" />;
  } else if (outline?.render?.kind === "unsupported") {
    body = <Fallback title={title} type={type} text={degradeNotice(outline)} />;
  } else if (scene) {
    body = <MaicSceneRenderer scene={scene} mode="playback" />;
  } else {
    body = <Fallback title={title} type={type} text="只显示标题，不用占位内容冒充正文。" />;
  }

  return <div className={cn(
    "relative w-full h-full flex flex-col",
    // 逐字对齐参考 `canvas-area.tsx` 的根节点：浅色模式是 **gray-50**，不是深色。
    // 写死深色会把 16:9 幻灯片包进一圈"影厅黑边"，与参考项目完全是两种观感。
    "bg-gray-50 dark:bg-gray-900",
  )}>
    <div className="flex-1 min-h-0 overflow-hidden flex items-center justify-center">
      {body}
    </div>
    {isPresenting ? null : <MaicRoundtable
      toolbar={<SceneToolbar
        index={index}
        total={total}
        sidebarCollapsed={sidebarCollapsed}
        onToggleSidebar={onToggleSidebar}
        onPrev={onPrev}
        onNext={onNext}
        narration={narration}
        actionSession={actionSession}
        playbackNotice={playbackNotice}
        onToggleActionTimeline={onToggleActionTimeline}
      />}
      messages={messages}
      busy={discussing}
      error={discussionError}
      prompt={topic}
      onPromptChange={onTopicChange}
      onStart={onStartDiscussion}
      sceneTitle={title}
    />}
  </div>;
}

/**
 * 画布底栏。容器与可用控件逐字移植参考项目 `components/canvas/canvas-toolbar.tsx`
 * （在 `canvas-area.tsx` 里它是**文档流内**的一条，不是浮层）：
 *
 *   shrink-0 h-9 px-2 bg-white/80 backdrop-blur-xl border-t border-gray-200/40
 *
 * 左侧是侧栏开关 + 页码，中间是上一场景 / 下一场景。
 *
 * **它现在住在圆桌面板的顶部条里。** 参考项目的 `canvas-area.tsx` 在播放态传
 * `hideToolbar={mode === 'playback'}`，一开始看像是"播放时没有工具栏"；但圆桌源码里
 * 有一行注释写明了原因——"Toolbar strip — merged from CanvasArea"。工具栏是被
 * **并进圆桌**，不是被丢弃：播放态的底部是「工具栏条（36px）+ 三栏交互区（156px）」
 * 共 192px。所以这里由 `MaicRoundtable` 的 `toolbar` 属性接住它。
 *
 * 参考工具栏还有白板、元素拾取、演示、停止讨论等控件，它们依赖圆桌流式 /
 * 画布 store，本仓库没有对应运行时，因此不渲染（不占位、也不放点了没反应的
 * 死按钮）。
 *
 * **讲解音频在这里。** 它不再是"输入一段文字去合成"，而是"这一页的讲解"：
 * 有音频就直接播放，没有就给一个「生成讲解」入口，生成中显示进度，失败显示
 * 原因并可重试。参考项目的那个静音按钮依赖 TTS 播放计划，本仓库没有该运行时，
 * 所以这里用真实的 `<audio>` 元素而不是复刻一个假按钮。
 */
function SceneToolbar({ index, total, sidebarCollapsed, onToggleSidebar, onPrev, onNext, narration, actionSession, playbackNotice, onToggleActionTimeline }) {
  const empty = total === 0;
  return <div className={cn(
    "shrink-0 h-9 px-2 flex items-center gap-2",
    "bg-white/80 dark:bg-gray-800/80 backdrop-blur-xl",
    "border-t border-gray-200/40 dark:border-gray-700/40",
  )}>
    <div className="flex items-center gap-1 shrink-0 pl-1">
      {onToggleSidebar ? <button
        type="button"
        onClick={onToggleSidebar}
        className={cn(
          ctrlBtn,
          sidebarCollapsed ? "text-gray-400 dark:text-gray-500" : "text-gray-600 dark:text-gray-300",
        )}
        aria-label="Toggle sidebar"
        aria-pressed={!sidebarCollapsed}
      >
        <LayoutList className="w-3.5 h-3.5" />
      </button> : null}
      <span className="text-[11px] text-gray-400 dark:text-gray-500 tabular-nums select-none font-medium">
        {empty ? 0 : index + 1}
        <span className="opacity-35 mx-px">/</span>
        {total}
      </span>
    </div>

    <NarrationControl narration={narration} />

    {onToggleActionTimeline ? <div className="flex items-center gap-1 min-w-0 shrink-0">
      <button
        type="button"
        onClick={onToggleActionTimeline}
        className={cn(ctrlBtn, "w-6 h-6 text-gray-500 dark:text-gray-400")}
        aria-label={actionSession?.status === "playing" ? "Pause scene actions" : "Play scene actions"}
        title={actionSession?.status === "playing" ? "暂停本页动作" : "播放本页动作"}
        data-testid="openmaic-action-playback-toggle"
      >
        {actionSession?.status === "playing" ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
      </button>
      {playbackNotice ? <output className="text-[10px] text-gray-400 dark:text-gray-500 truncate max-w-40" data-testid="openmaic-action-playback-status">
        {playbackNotice}
      </output> : null}
    </div> : null}

    <div className="flex-1 flex items-center justify-center min-w-0">
      <button
        type="button"
        onClick={onPrev}
        disabled={!onPrev}
        className={cn(ctrlBtn, "w-6 h-6 text-gray-500 dark:text-gray-400 disabled:opacity-20 disabled:pointer-events-none")}
        aria-label="Previous scene"
        title="上一场景"
      >
        <ChevronLeft className="w-3.5 h-3.5" />
      </button>
      <button
        type="button"
        onClick={onNext}
        disabled={!onNext}
        className={cn(ctrlBtn, "w-6 h-6 text-gray-500 dark:text-gray-400 disabled:opacity-20 disabled:pointer-events-none")}
        aria-label="Next scene"
        title="下一场景"
      >
        <ChevronRight className="w-3.5 h-3.5" />
      </button>
    </div>
  </div>;
}

/**
 * 讲解音频控件。
 *
 * 五种状态各有各的界面，**没有一种会把失败伪装成"没有音频"**：
 * - `checking`：细的加载指示，不占位成按钮；
 * - `generating`：禁用按钮 + 说明，避免重复提交；
 * - `ready`：真实的 `<audio controls>`，由浏览器负责播放；
 * - `none`：说明"这一页没有可讲解的文字"，且不再给生成入口（点了也没用）；
 * - `error`：显示原因 + 可重试的「重新生成讲解」。
 *
 * 音频元素只在 `ready` 时挂载，因此换场景后旧音频会随组件消失，不可能串页。
 */
function NarrationControl({ narration }) {
  if (!narration) return null;
  const { state, error, notice, audioUrl, generate } = narration;
  if (state === "idle") return null;

  return <div className="flex items-center gap-2 min-w-0 shrink-0">
    {state === "checking" ? <span className="text-[11px] text-gray-400 dark:text-gray-500 select-none">正在检查讲解…</span> : null}

    {narration.ready && audioUrl ? <audio
      className="h-7 max-w-[240px]"
      controls
      preload="none"
      src={audioUrl}
      data-testid="narration-audio"
      aria-label="本页讲解音频"
    /> : null}

    {state === "generating" ? <span className="flex items-center gap-1.5 text-[11px] text-gray-500 dark:text-gray-400 select-none" role="status">
      <span className="loading-orb" style={{ width: 12, height: 12 }} />
      正在生成讲解…
    </span> : null}

    {canGenerateNarration({ state }) ? <button
      type="button"
      onClick={() => void generate()}
      className={cn(ctrlBtn, "h-6 px-2 gap-1 text-[11px] text-gray-600 dark:text-gray-300")}
      data-testid="narration-generate"
      title={state === "error" ? error || "重新生成这一页的讲解" : "为这一页生成讲解音频"}
    >
      <Icon name="PhSpeakerHigh" size={13} />
      {state === "error" ? "重新生成讲解" : "生成讲解"}
    </button> : null}

    {state === "none" ? <span className="text-[11px] text-gray-400 dark:text-gray-500 select-none truncate" role="status">
      {notice || "这一页没有可讲解的文字"}
    </span> : null}

    {state === "error" && error ? <span className="text-[11px] text-amber-600 dark:text-amber-400 truncate" role="alert" title={error}>
      {error}
    </span> : null}

    {narration.ready && narration.truncated ? <span className="text-[11px] text-gray-400 dark:text-gray-500 select-none" role="status">
      原文较长，已截断
    </span> : null}
  </div>;
}

function Fallback({ title, type, text }) {
  return <div className="flex flex-col items-center gap-3 text-center max-w-md px-6">
    <Icon name="PhWarningCircle" size={26} />
    <small className="text-xs uppercase tracking-wide text-gray-400 dark:text-gray-500">
      {SCENE_TYPE_LABELS[type] || type}
    </small>
    <strong className="text-base font-medium text-gray-800 dark:text-gray-200">「{title}」当前无法播放</strong>
    <p className="text-sm text-gray-500 dark:text-gray-400">{text}</p>
  </div>;
}

/**
 * 轮询讨论任务直到终态。
 *
 * 三个刻意的约束：
 * - **有上限。** 服务端若一直回 `queued`，没有上限的轮询会把用户锁在"正在组织讨论…"
 *   上；到点返回最后一个状态，让调用方按 `status !== 'completed'` 如实报错。
 * - **可中止。** 传进来的 `isCurrent()` 在换场景/重复提交后为假时立刻停——否则旧任务
 *   会一直占用网络与计时器，直到撞上自己的上限。
 * - **不用递归 setTimeout。** 循环 + `await` 天然随函数结束而停止，不需要在卸载时
 *   逐个清理计时器。
 */
async function waitForDiscussionJob(courseId, jobId, isCurrent) {
  const deadline = Date.now() + 120000;
  let job = null;
  while (Date.now() < deadline) {
    job = await api.getOpenMAICJob(courseId, jobId);
    if (!isCurrent()) return null;
    if (!job || !["queued", "running"].includes(job.status)) return job;
    await new Promise((resolve) => { window.setTimeout(resolve, 900); });
  }
  return job;
}

/**
 * 舞台文档 → `{ [sceneId]: scene }`。
 *
 * `GET .../stages/{id}` 返回 `{ document: { scenes: [...] } }`；拿不到就返回空表，
 * 调用方据此显示"读不到"而不是编造内容。非数组、缺 id 的条目一律跳过——半个
 * 索引比没有索引更危险，它会让某些场景看起来"存在但没有内容"。
 */
function indexScenesById(stageDocument) {
  const scenes = stageDocument?.document?.scenes;
  if (!Array.isArray(scenes)) return {};
  const index = {};
  for (const entry of scenes) {
    if (entry && typeof entry.id === "string" && entry.id) index[entry.id] = entry;
  }
  return index;
}

/**
 * 侧栏里的幻灯片缩略图。
 *
 * 复用播放画布而不是另写一个渲染器：两者共用同一份画布 JSON 和同一套元素渲染件，
 * 因此**缩略图与实际播放内容不可能不一致**。参考项目在这里用的是独立的
 * `SlideThumbnail`，本仓库没有该组件；画布盒由侧栏给出（aspect-video +
 * overflow-hidden），这里的 `h-full w-full` 让画布自行 contain 缩放并居中。
 *
 * 没有 `elements` 的历史画布返回 `null`：让移植层的占位分支接管，而不是画一块
 * 空白色矩形冒充缩略图。
 */
function SlideThumbnail({ canvas }) {
  const elements = canvas && Array.isArray(canvas.elements) ? canvas.elements : null;
  if (!elements || elements.length === 0) return null;
  return <div className="h-full w-full">
    <MaicSlideSurface canvas={canvas} effectsEnabled={false} />
  </div>;
}
