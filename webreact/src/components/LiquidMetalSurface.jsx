import { useEffect, useRef, useState } from "react";
import { mountLiquidMetal } from "./liquidMetalScene";

export default function LiquidMetalSurface({
  children,
  className = "",
  contentClassName = "",
  active = false,
  defer = true,
  disableEffects = false,
  ...props
}) {
  const stageRef = useRef(null);
  const activeRef = useRef(active);
  const interactionRef = useRef({ pointer: false, focus: false });
  const [interacting, setInteracting] = useState(false);
  activeRef.current = active;
  const shouldMount = !disableEffects && (!defer || active || interacting);

  useEffect(() => {
    if (!shouldMount) return undefined;
    return mountLiquidMetal(stageRef.current, {
      getActive: () => activeRef.current,
      getEngaged: () => activeRef.current || interactionRef.current.pointer || interactionRef.current.focus,
    });
  }, [shouldMount]);

  const syncInteraction = () => {
    if (defer && !disableEffects) setInteracting(interactionRef.current.pointer || interactionRef.current.focus);
  };
  const setPointer = (value) => {
    interactionRef.current.pointer = value;
    syncInteraction();
  };
  const setFocus = (value) => {
    interactionRef.current.focus = value;
    syncInteraction();
  };

  return (
    <div
      ref={stageRef}
      className={`sylva-liquid-stage sylva-liquid-stage--surface ${className}`.trim()}
      data-liquid-metal="surface"
      data-active={active ? "true" : undefined}
      {...props}
      onPointerEnter={(event) => { setPointer(true); props.onPointerEnter?.(event); }}
      onPointerLeave={(event) => { setPointer(false); props.onPointerLeave?.(event); }}
      onPointerDown={(event) => { setPointer(true); props.onPointerDown?.(event); }}
      onFocusCapture={(event) => { setFocus(true); props.onFocusCapture?.(event); }}
      onBlurCapture={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setFocus(false);
        props.onBlurCapture?.(event);
      }}
    >
      <span className="sylva-liquid-plate" aria-hidden="true" />
      {shouldMount && <canvas className="sylva-liquid-fx" aria-hidden="true" />}
      <div className={`sylva-liquid-control sylva-liquid-surface-content ${contentClassName}`.trim()}>
        {children}
      </div>
    </div>
  );
}
