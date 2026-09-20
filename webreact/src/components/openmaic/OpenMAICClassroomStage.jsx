import React from "react";
import { Button } from "../Primitives.jsx";
import { Icon } from "../Icon.jsx";
import * as api from "../../data/api.js";
import { MaicClassroomShell } from "../../maic/classroom/index.js";
import { MaicSceneRenderer } from "../../maic/scene/index.js";
import {
  degradeNotice,
  describePlaybackError,
  normalizePlayback,
  sandboxPolicyFor,
} from "../../features/openmaic/playerModel.js";
import { SCENE_TYPE_LABELS } from "../../features/openmaic/editorModel.js";
import { useNarrowViewport } from "../../features/openmaic/workbenchLayoutModel.js";

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
  const [scene, setScene] = React.useState(null);
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
  const [sceneLoading, setSceneLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const epoch = React.useRef(0);

  const load = React.useCallback(async () => {
    const mine = (epoch.current += 1);
    setLoading(true);
    setError("");
    try {
      const payload = await api.getOpenMAICStagePlayback(courseId, workspaceId, stageId);
      if (mine !== epoch.current) return; // 迟到的响应不得写进新上下文
      const normalized = normalizePlayback(payload);
      setPlan(normalized);
      setIndex(normalized.startIndex);
    } catch (failure) {
      if (mine !== epoch.current) return;
      setPlan(null);
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
    setScene(null);
  }, [courseId, workspaceId, stageId]);

  const scenes = plan?.scenes || [];
  const current = scenes[index] || null;
  const currentId = current?.id || "";

  React.useEffect(() => {
    if (!currentId) {
      setScene(null);
      return;
    }
    const mine = epoch.current;
    let cancelled = false;
    setSceneLoading(true);
    void (async () => {
      try {
        const payload = await api.getOpenMAICStageScene(courseId, workspaceId, stageId, currentId);
        if (cancelled || mine !== epoch.current) return;
        setScene(payload);
      } catch {
        // 读不到正文就只显示标题，不编造内容。
        if (!cancelled && mine === epoch.current) setScene(null);
      } finally {
        if (!cancelled && mine === epoch.current) setSceneLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [courseId, workspaceId, stageId, currentId]);

  const go = React.useCallback((next) => {
    setIndex((currentIndex) => (next < 0 || next > scenes.length - 1 ? currentIndex : next));
  }, [scenes.length]);

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

  return <div className="maic-root flex-1 min-h-0 min-w-0 flex">
    <MaicClassroomShell
      title={plan?.title || fallbackTitle}
      scenes={scenes}
      currentSceneId={currentId}
      onSelectScene={(id) => {
        const next = scenes.findIndex((entry) => entry.id === id);
        if (next >= 0) go(next);
      }}
      onPrevScene={index > 0 ? () => go(index - 1) : undefined}
      onNextScene={index < scenes.length - 1 ? () => go(index + 1) : undefined}
      sidebarCollapsed={collapsed}
      onToggleSidebar={() => setCollapsed((value) => !value)}
      // 参考项目侧栏顶部是 `<img src="/logo-horizontal.png">`。目标仓库没有这个
      // 品牌图，直接沿用会渲染成一张破图（alt 文本裸露、占据 h-6 高度）。把上游
      // 二进制搬进来要走 third_party 的 LICENSE/NOTICE/清单流程，不属于本次范围，
      // 所以用同槽位的文字字标替代：视觉角色一致（一行品牌标识），且不会破图。
      sidebarProps={{ headerSlot: <span className="text-[15px] font-black tracking-tight text-gray-900 dark:text-gray-100">OpenMAIC</span> }}
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
      headerActions={<span className="text-xs text-muted-foreground">{index + 1} / {scenes.length}</span>}
    >
      <SceneStage
        scene={scene}
        outline={current}
        loading={sceneLoading}
        onPrev={index > 0 ? () => go(index - 1) : undefined}
        onNext={index < scenes.length - 1 ? () => go(index + 1) : undefined}
      />
    </MaicClassroomShell>
  </div>;
}

/** 场景类型 → 中文标签，与工作台目录用语同源（`editorModel.SCENE_TYPE_LABELS`）。 */
/**
 * 画布区。只负责**如实执行**服务端给出的渲染决定：
 * 原生交给移植来的渲染器，沙箱交给最小 sandbox 的 iframe，其余说清缺什么。
 */
function SceneStage({ scene, outline, loading, onPrev, onNext }) {
  const title = outline?.title || "";
  const type = outline?.type || "unknown";
  const policy = sandboxPolicyFor(outline?.render);

  const sandboxHtml = typeof scene?.content?.html === "string" ? scene.content.html : "";
  const sandboxUrl = typeof scene?.content?.url === "string" ? scene.content.url : "";

  let body;
  if (loading) {
    body = <div className="flex flex-col items-center gap-3 text-gray-400">
      <span className="loading-orb" />
      <p>正在读取场景内容…</p>
    </div>;
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

  return <div className="relative w-full h-full flex flex-col bg-gray-900">
    <div className="flex-1 min-h-0 overflow-hidden flex items-center justify-center">
      {body}
    </div>
    {(onPrev || onNext) ? <div className="shrink-0 flex items-center justify-center gap-2 py-3 bg-gray-950/60">
      <Button type="button" variant="secondary" size="sm" disabled={!onPrev} onClick={onPrev}>上一场景</Button>
      <Button type="button" variant="secondary" size="sm" disabled={!onNext} onClick={onNext}>下一场景</Button>
    </div> : null}
  </div>;
}

function Fallback({ title, type, text }) {
  return <div className="flex flex-col items-center gap-3 text-center max-w-md px-6 text-gray-300">
    <Icon name="PhWarningCircle" size={26} />
    <small className="text-xs uppercase tracking-wide text-gray-500">
      {SCENE_TYPE_LABELS[type] || type}
    </small>
    <strong className="text-base font-medium">「{title}」当前无法播放</strong>
    <p className="text-sm text-gray-400">{text}</p>
  </div>;
}
