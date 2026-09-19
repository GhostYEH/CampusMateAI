import React from "react";
import { Button, Panel, SectionHeading } from "../Primitives.jsx";
import { Icon } from "../Icon.jsx";
import QuizRuntimePanel from "./QuizRuntimePanel.jsx";
import SimulationRuntimePanel from "./SimulationRuntimePanel.jsx";
import PblRuntimePanel from "./PblRuntimePanel.jsx";
import * as api from "../../data/api.js";
import {
  SCENE_TYPE_LABELS,
} from "../../features/openmaic/editorModel.js";
import {
  actionTimeline,
  degradeNotice,
  describePlaybackError,
  normalizePlayback,
  playerNavigation,
  sandboxPolicyFor,
} from "../../features/openmaic/playerModel.js";

/**
 * 场景播放器。
 *
 * 只做三件真实的事：
 *
 * - 原生场景由 CampusMate 自己渲染（读取真实场景内容，不做假动画）；
 * - 服务端判定为沙箱内容的场景放进 `sandbox` iframe，沙箱串由服务端给出且
 *   绝不包含 `allow-same-origin`；
 * - 服务端判定无法渲染的场景显示**具体缺什么**，而不是空白或死按钮。
 *
 * `sceneId` 变化即恢复位置：刷新后回到同一个场景。
 */
export default function StagePlayerPanel({ courseId, workspaceId, stageId, startSceneId = "", onClose }) {
  const [plan, setPlan] = React.useState(null);
  const [index, setIndex] = React.useState(0);
  const [scene, setScene] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");
  const epoch = React.useRef(0);

  const load = React.useCallback(async () => {
    const mine = (epoch.current += 1);
    setLoading(true);
    setError("");
    try {
      const payload = await api.getOpenMAICStagePlayback(courseId, workspaceId, stageId, {
        sceneId: startSceneId || null,
      });
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
  }, [courseId, workspaceId, stageId, startSceneId]);

  React.useEffect(() => {
    void load();
  }, [load]);

  const nav = playerNavigation(plan?.scenes || [], index);
  const currentScene = plan?.scenes?.[nav.index] || null;
  const policy = sandboxPolicyFor(currentScene?.render);

  // 场景正文只从授权的场景端点取：播放计划是导航面，不携带正文。
  React.useEffect(() => {
    if (!currentScene) {
      setScene(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const payload = await api.getOpenMAICStageScene(courseId, workspaceId, stageId, currentScene.id);
        if (!cancelled) setScene(payload);
      } catch {
        // 读不到正文就只显示标题，不编造内容。
        if (!cancelled) setScene(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [courseId, workspaceId, stageId, currentScene]);

  const timeline = actionTimeline(currentScene);
  const sandboxHtml = typeof scene?.content?.html === "string" ? scene.content.html : "";
  const sandboxUrl = typeof scene?.content?.url === "string" ? scene.content.url : "";

  return <Panel className="openmaic-player">
    <SectionHeading
      title="场景播放"
      detail={plan ? `${plan.title} · 第 ${nav.total ? nav.index + 1 : 0}/${nav.total} 个场景` : "读取中"}
    />

    <div className="openmaic-player__toolbar">
      <Button type="button" variant="secondary" disabled={!nav.hasPrev} onClick={() => setIndex(nav.prevIndex ?? 0)}>上一场景</Button>
      <Button type="button" disabled={!nav.hasNext} onClick={() => setIndex(nav.nextIndex ?? nav.index)}>下一场景</Button>
      <Button type="button" variant="quiet" onClick={load}>重新读取</Button>
      {onClose ? <Button type="button" variant="quiet" onClick={onClose}>关闭播放器</Button> : null}
    </div>

    {error ? <p className="openmaic-hint openmaic-hint--error" role="alert">{error}</p> : null}
    {loading ? <p className="openmaic-hint">正在读取播放计划…</p> : null}

    {currentScene ? <>
      <div className="openmaic-player__stage" data-render-kind={currentScene.render.kind}>
        <header className="openmaic-player__title">
          <span className="openmaic-player__type">{SCENE_TYPE_LABELS[currentScene.type] || currentScene.type}</span>
          <strong>{currentScene.title}</strong>
          {currentScene.multiAgent ? <small>含智能体讨论</small> : null}
          {currentScene.whiteboards ? <small>{currentScene.whiteboards} 块白板</small> : null}
        </header>

        {policy.allowIframe && currentScene.render.widget_type !== "simulation" ? <iframe
          className="openmaic-player__frame"
          title={currentScene.title}
          sandbox={policy.sandbox}
          referrerPolicy="no-referrer"
          {...(currentScene.render.kind === "sandbox-html"
            ? { srcDoc: sandboxHtml }
            : { src: sandboxUrl })}
        /> : null}

        {(currentScene.render.kind === "native" || currentScene.render.widget_type === "simulation") ? <NativeScene scene={scene} fallbackTitle={currentScene.title} /> : null}

        {currentScene.render.kind === "unsupported" ? <div className="openmaic-player__degraded" role="status">
          <Icon name="PhWarningCircle" size={22} />
          <div>
            <strong>这个场景当前无法播放</strong>
            <p>{degradeNotice(currentScene)}</p>
          </div>
        </div> : null}
      </div>

      {timeline.length ? <ol className="openmaic-player__timeline" aria-label="场景动作时间线">
        {timeline.map((step) => <li key={step.actionId}>
          <span>{step.type}</span>
          <small>{step.blocking ? "需等待完成" : "即发即忘"}</small>
        </li>)}
      </ol> : null}

      {currentScene.droppedActions.length ? <p className="openmaic-hint">
        本场景有 {currentScene.droppedActions.length} 个动作在当前场景类型下不会执行（例如聚光灯只对幻灯片有效）。
      </p> : null}
    </> : null}
  </Panel>;
}

/**
 * 原生场景的最小真实渲染。
 *
 * 只呈现文档里真实存在的内容：quiz 呈现真实题目，slide 呈现真实画板块数。
 * 读不到正文时只显示标题，不编造内容。
 */
function NativeScene({ scene, fallbackTitle }) {
  const content = scene?.content;
  if (!content) {
    return <p className="openmaic-hint">「{fallbackTitle}」的正文暂时读不到，仅显示标题。</p>;
  }
  if (content.type === "quiz") return <QuizRuntimePanel questions={content.questions} sceneId={scene?.id || ""} />;
  if (content.type === "pbl") return <PblRuntimePanel content={content} sceneId={scene?.id || ""} />;
  if (content.type === "interactive" && content.widgetType === "simulation") return <SimulationRuntimePanel content={content} sceneId={scene?.id || ""} />;
  if (content.type === "slide") {
    const canvas = content.canvas || {};
    const elements = Array.isArray(canvas.elements) ? canvas.elements : [];
    const images = elements.filter((element) => typeof element?.dataUri === "string" && /^data:image\/(png|jpeg|gif|webp);base64,/i.test(element.dataUri));
    return <div className="openmaic-player__slide">
      {canvas.title ? <h3>{String(canvas.title)}</h3> : null}
      {canvas.body ? <p>{String(canvas.body)}</p> : null}
      {elements.length ? <ul aria-label="幻灯片内容元素">{elements.map((element, index) => <li key={`${element.kind || "element"}-${index}`}>
        {images.includes(element) ? <img src={element.dataUri} alt={String(element.alt || "幻灯片图片")} /> : null}
        {element.text || element.value || element.label ? <span>{String(element.text || element.value || element.label)}</span> : null}
      </li>)}</ul> : <p className="openmaic-hint">这张幻灯片还没有内容元素。</p>}
      {Array.isArray(scene.whiteboards) && scene.whiteboards.length ? <div className="openmaic-player__whiteboards" aria-label="白板内容">
        {scene.whiteboards.map((board, index) => <article key={board.id || index}><strong>{board.title || `白板 ${index + 1}`}</strong><small>{Array.isArray(board.elements) ? `${board.elements.length} 个绘制元素` : "暂无绘制元素"}</small></article>)}
      </div> : null}
    </div>;
  }
  return <p className="openmaic-hint">该场景类型的内容由 CampusMate 原生渲染。</p>;
}
