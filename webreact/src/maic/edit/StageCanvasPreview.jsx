import React from "react";
import { MaicSlideSurface } from "../slide/MaicSlideSurface.jsx";

/**
 * P1-A edit surface: a read-only view of the selected scene's real canvas.
 *
 * The editor deliberately shares MaicSlideSurface with classroom playback.
 * Keeping this boundary read-only leaves selection, drag, and command wiring
 * for the following editor slices while making the workbench preview truthful.
 */
export default function StageCanvasPreview({ scene, onMoveElement }) {
  const rootRef = React.useRef(null);
  const dragRef = React.useRef(null);
  const [selectedElementId, setSelectedElementId] = React.useState("");
  const [dragPosition, setDragPosition] = React.useState(null);
  const [selectionRect, setSelectionRect] = React.useState(null);
  const content = scene?.content;
  const canvas = content?.type === "slide" ? content.canvas : null;
  const elements = Array.isArray(canvas?.elements) ? canvas.elements : [];
  const selectedElement = elements.find((element) => element?.id === selectedElementId) || null;

  React.useEffect(() => {
    if (!selectedElementId || !selectedElement || !rootRef.current) {
      setSelectionRect(null);
      return;
    }
    const target = [...rootRef.current.querySelectorAll("[data-maic-element-id]")]
      .find((entry) => entry.getAttribute("data-maic-element-id") === selectedElementId);
    if (!target) {
      setSelectionRect(null);
      return;
    }
    const rootBox = rootRef.current.getBoundingClientRect();
    const targetBox = target.getBoundingClientRect();
    const scaleX = Number.isFinite(selectedElement.width) && selectedElement.width > 0
      ? targetBox.width / selectedElement.width
      : rootBox.width / (Number(canvas?.width) || 1000);
    const scaleY = Number.isFinite(selectedElement.height) && selectedElement.height > 0
      ? targetBox.height / selectedElement.height
      : rootBox.height / (Number(canvas?.height) || 562.5);
    setSelectionRect({
      left: targetBox.left - rootBox.left,
      top: targetBox.top - rootBox.top,
      width: targetBox.width,
      height: targetBox.height,
      scaleX: Number.isFinite(scaleX) && scaleX > 0 ? scaleX : 1,
      scaleY: Number.isFinite(scaleY) && scaleY > 0 ? scaleY : 1,
    });
  }, [canvas, selectedElement, selectedElementId]);

  React.useEffect(() => {
    if (selectedElementId && !selectedElement) setSelectedElementId("");
  }, [selectedElement, selectedElementId]);

  const finishDrag = React.useCallback((event, cancelled = false) => {
    const drag = dragRef.current;
    if (!drag || (event && event.pointerId !== drag.pointerId)) return;
    dragRef.current = null;
    setDragPosition(null);
    if (!cancelled && drag.moved && Number.isFinite(drag.left) && Number.isFinite(drag.top)) {
      // The command enters the parent buffer only here, after pointerup.
      onMoveElement?.(drag.elementId, drag.left, drag.top);
    }
  }, [onMoveElement]);

  const handlePointerDown = React.useCallback((event) => {
    if (!rootRef.current) return;
    const target = event.target?.closest?.("[data-maic-element-id]");
    if (!target || !rootRef.current.contains(target)) {
      setSelectedElementId("");
      setSelectionRect(null);
      return;
    }
    const elementId = target.getAttribute("data-maic-element-id") || "";
    const element = elements.find((entry) => entry?.id === elementId);
    if (!element || !Number.isFinite(element.left) || !Number.isFinite(element.top)) {
      // Non-slide content and elements without finite coordinates remain read-only.
      setSelectedElementId("");
      setSelectionRect(null);
      return;
    }
    event.stopPropagation();
    setSelectedElementId(elementId);
    const rootBox = rootRef.current.getBoundingClientRect();
    const targetBox = target.getBoundingClientRect();
    const scaleX = Number.isFinite(element.width) && element.width > 0
      ? targetBox.width / element.width
      : rootBox.width / (Number(canvas?.width) || 1000);
    const scaleY = Number.isFinite(element.height) && element.height > 0
      ? targetBox.height / element.height
      : rootBox.height / (Number(canvas?.height) || 562.5);
    dragRef.current = {
      pointerId: event.pointerId,
      elementId,
      startX: event.clientX,
      startY: event.clientY,
      originLeft: element.left,
      originTop: element.top,
      left: element.left,
      top: element.top,
      scaleX: Number.isFinite(scaleX) && scaleX > 0 ? scaleX : 1,
      scaleY: Number.isFinite(scaleY) && scaleY > 0 ? scaleY : 1,
      moved: false,
    };
    setSelectionRect({
      left: targetBox.left - rootBox.left,
      top: targetBox.top - rootBox.top,
      width: targetBox.width,
      height: targetBox.height,
      scaleX: Number.isFinite(scaleX) && scaleX > 0 ? scaleX : 1,
      scaleY: Number.isFinite(scaleY) && scaleY > 0 ? scaleY : 1,
    });
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }, [canvas, elements]);

  const handlePointerMove = React.useCallback((event) => {
    const drag = dragRef.current;
    if (!drag || event.pointerId !== drag.pointerId) return;
    const left = drag.originLeft + (event.clientX - drag.startX) / drag.scaleX;
    const top = drag.originTop + (event.clientY - drag.startY) / drag.scaleY;
    drag.left = left;
    drag.top = top;
    drag.moved = drag.moved || Math.abs(left - drag.originLeft) > 0.01 || Math.abs(top - drag.originTop) > 0.01;
    setDragPosition({ left, top });
  }, []);

  const renderedSelection = selectedElement && selectionRect
    ? {
      ...selectionRect,
      left: selectionRect.left + ((dragPosition?.left ?? selectedElement.left) - selectedElement.left) * selectionRect.scaleX,
      top: selectionRect.top + ((dragPosition?.top ?? selectedElement.top) - selectedElement.top) * selectionRect.scaleY,
    }
    : null;

  return <div
    ref={rootRef}
    className="maic-edit-canvas flex flex-col h-full"
    data-maic-edit-canvas="true"
    data-testid="openmaic-editor-canvas"
    data-scene-id={scene?.id || ""}
    aria-label={scene ? `编辑预览：${scene.title || "未命名场景"}` : "编辑预览"}
    onPointerDown={handlePointerDown}
    onPointerMove={handlePointerMove}
    onPointerUp={finishDrag}
    onPointerCancel={(event) => finishDrag(event, true)}
    style={{ position: "relative", touchAction: "none" }}
  >
    {scene && content?.type === "slide" && elements.length ? <div className="maic-edit-canvas__surface flex-1 overflow-hidden relative h-full w-full">
      <MaicSlideSurface canvas={canvas} sceneId={scene.id} sceneData={scene} />
    </div> : <div className="maic-edit-canvas__empty" role="status">
      <strong>{scene ? (scene.title || "未命名场景") : "选择一个场景"}</strong>
      <p>{scene && content?.type === "slide" ? "这张幻灯片还没有可显示的画布元素。" : "当前场景类型暂未接入编辑画布预览。"}</p>
    </div>}
    {renderedSelection ? <div
      className="maic-edit-canvas__selection"
      data-testid="openmaic-selected-element"
      data-selected-element-id={selectedElement.id}
      aria-label={`已选中元素：${selectedElement.id}`}
      style={{
        left: renderedSelection.left,
        top: renderedSelection.top,
        width: renderedSelection.width,
        height: renderedSelection.height,
      }}
    /> : null}
  </div>;
}
