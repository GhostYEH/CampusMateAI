import React from "react";
import { MaicSlideSurface } from "../slide/MaicSlideSurface.jsx";

/**
 * P1-A edit surface: a read-only view of the selected scene's real canvas.
 *
 * The editor deliberately shares MaicSlideSurface with classroom playback.
 * Keeping this boundary read-only leaves selection, drag, and command wiring
 * for the following editor slices while making the workbench preview truthful.
 */
export default function StageCanvasPreview({ scene }) {
  const content = scene?.content;
  const canvas = content?.type === "slide" ? content.canvas : null;
  const elements = Array.isArray(canvas?.elements) ? canvas.elements : [];

  return <div
    className="maic-edit-canvas flex flex-col h-full"
    data-maic-edit-canvas="true"
    data-testid="openmaic-editor-canvas"
    data-scene-id={scene?.id || ""}
    aria-label={scene ? `编辑预览：${scene.title || "未命名场景"}` : "编辑预览"}
  >
    {scene && content?.type === "slide" && elements.length ? <div className="maic-edit-canvas__surface flex-1 overflow-hidden relative h-full w-full">
      <MaicSlideSurface canvas={canvas} sceneId={scene.id} sceneData={scene} />
    </div> : <div className="maic-edit-canvas__empty" role="status">
      <strong>{scene ? (scene.title || "未命名场景") : "选择一个场景"}</strong>
      <p>{scene && content?.type === "slide" ? "这张幻灯片还没有可显示的画布元素。" : "当前场景类型暂未接入编辑画布预览。"}</p>
    </div>}
  </div>;
}
