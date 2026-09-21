import { useCallback, useEffect, useRef } from "react";

/**
 * 分栏拖拽手柄。
 *
 * 用 pointer capture 而不是 document 事件：捕获之后即使指针移动到别的元素上，
 * 事件仍然回到这个手柄，拖动不会在划过别处时断掉。
 *
 * 两个细节来自参考项目的实测：
 * - **阈值。** 按下就改宽度会让"点一下"变成"拖了 1px"，所以位移小于 3px 不提交。
 * - **只认主键。** 右键/中键按下不启动拖动。
 */
const DRAG_THRESHOLD_PX = 3;

export default function ResizeHandle({ label, edge = "right", value, min, max, onCommit, onReset }) {
  const dragging = useRef(false);
  const origin = useRef({ x: 0, value: 0 });
  const cleanup = useRef(null);

  const stop = useCallback(() => {
    dragging.current = false;
    document.documentElement.removeAttribute("data-ow-resizing");
    cleanup.current?.();
    cleanup.current = null;
  }, []);

  useEffect(() => stop, [stop]);

  const onPointerDown = (event) => {
    if (event.button !== 0) return;
    const handle = event.currentTarget;
    origin.current = { x: event.clientX, value };
    dragging.current = false;

    const move = (moveEvent) => {
      const delta = moveEvent.clientX - origin.current.x;
      // 先过阈值再算拖动，避免"点击"被误判成"轻微拖动"。
      if (!dragging.current) {
        if (Math.abs(delta) < DRAG_THRESHOLD_PX) return;
        dragging.current = true;
        handle.dataset.owDrag = "true";
        // 拖动期间锁住光标与选中：不锁的话指针划过其它元素时光标会闪。
        document.documentElement.setAttribute("data-ow-resizing", "true");
      }
      const raw = edge === "right" ? origin.current.value + delta : origin.current.value - delta;
      onCommit?.(Math.round(Math.max(min, Math.min(max, raw))));
    };

    const up = () => { handle.dataset.owDrag = "false"; stop(); };

    try { handle.setPointerCapture(event.pointerId); } catch { /* 不支持的浏览器走 document */ }
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
    cleanup.current = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
    };
  };

  const onKeyDown = (event) => {
    const step = event.shiftKey ? 40 : 12;
    if (event.key === "ArrowLeft") { event.preventDefault(); onCommit?.(Math.round(Math.max(min, Math.min(max, value - step)))); }
    else if (event.key === "ArrowRight") { event.preventDefault(); onCommit?.(Math.round(Math.max(min, Math.min(max, value + step)))); }
    else if (event.key === "Home") { event.preventDefault(); onCommit?.(min); }
    else if (event.key === "End") { event.preventDefault(); onCommit?.(max); }
    else if (event.key === "Enter") { event.preventDefault(); onReset?.(); }
  };

  return <div
    className="ow-resize"
    role="separator"
    aria-orientation="vertical"
    aria-label={label}
    aria-valuenow={Math.round(value)}
    aria-valuemin={min}
    aria-valuemax={max}
    tabIndex={0}
    data-edge={edge}
    data-ow-drag="false"
    onPointerDown={onPointerDown}
    onDoubleClick={onReset}
    onKeyDown={onKeyDown}
  >
    <span className="ow-resize__thread" aria-hidden="true" />
  </div>;
}
