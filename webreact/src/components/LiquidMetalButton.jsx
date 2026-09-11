import { useEffect, useRef, useState } from "react";
import { mountLiquidMetal } from "./liquidMetalScene";

function stageModifier(className, variant) {
  if (variant === "nav") return "sylva-liquid-stage--nav";
  if (className.includes("sylva-priority-more")) return "sylva-liquid-stage--wide";
  if (className.includes("sylva-card-link")) return "sylva-liquid-stage--compact";
  return "sylva-liquid-stage--overview";
}

export default function LiquidMetalButton({
  children,
  className = "",
  variant,
  active = false,
  defer = true,
  disableEffects = false,
  maxFps,
  dprCap,
  ...props
}) {
  const stageRef = useRef(null);
  const activeRef = useRef(active);
  const interactionRef = useRef({ pointer: false, focus: false });
  activeRef.current = active;
  const [interacting, setInteracting] = useState(false);
  const shouldMount = !disableEffects && (!defer || active || interacting);

  useEffect(() => {
    if (!shouldMount) return undefined;
    return mountLiquidMetal(stageRef.current, {
      getActive: () => activeRef.current,
      getEngaged: () => activeRef.current || interactionRef.current.pointer || interactionRef.current.focus,
      maxFps,
      dprCap,
    });
  }, [shouldMount, maxFps, dprCap]);

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
    <span
      ref={stageRef}
      className={`sylva-liquid-stage ${stageModifier(className, variant)}`}
      data-liquid-metal="explore"
      data-active={active ? "true" : undefined}
    >
      <span className="sylva-liquid-plate" aria-hidden="true" />
      {shouldMount && <canvas className="sylva-liquid-fx" aria-hidden="true" />}
      <button
        type="button"
        className={`sylva-liquid-control ${className}`.trim()}
        {...props}
        onPointerEnter={(event) => { setPointer(true); props.onPointerEnter?.(event); }}
        onPointerLeave={(event) => { setPointer(false); props.onPointerLeave?.(event); }}
        onPointerDown={(event) => { setPointer(true); props.onPointerDown?.(event); }}
        onFocus={(event) => { setFocus(true); props.onFocus?.(event); }}
        onBlur={(event) => { setFocus(false); props.onBlur?.(event); }}
      >
        {children}
      </button>
    </span>
  );
}
