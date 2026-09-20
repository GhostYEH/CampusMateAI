import React from "react";
import { Button } from "../Primitives.jsx";
import { Icon } from "../Icon.jsx";
import * as api from "../../data/api.js";
import { MaicClassroomShell } from "../../maic/classroom/index.js";
import { MaicSceneRenderer } from "../../maic/scene/index.js";
import { MaicSlideSurface } from "../../maic/slide/index.js";
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
  const epoch = React.useRef(0);

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
      // 参考项目侧栏顶部是 `<img src="/logo-horizontal.png">`。目标仓库没有这个
      // 品牌图，直接沿用会渲染成一张破图（alt 文本裸露、占据 h-6 高度）。把上游
      // 二进制搬进来要走 third_party 的 LICENSE/NOTICE/清单流程，不属于本次范围，
      // 所以用同槽位的文字字标替代：视觉角色一致（一行品牌标识），且不会破图。
      sidebarProps={{
        headerSlot: <span className="text-[15px] font-black tracking-tight text-gray-900 dark:text-gray-100">OpenMAIC</span>,
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
    <MaicSlideSurface canvas={canvas} />
  </div>;
}
