import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { mountLiquidMetal } from "./liquidMetalScene";

const useIsomorphicLayoutEffect = typeof window === "undefined" ? useEffect : useLayoutEffect;

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
  useSharedNavigationRenderer = false,
  maxFps,
  dprCap,
  onLiquidStageReady,
  onLiquidTargetEnter,
  onLiquidTargetLeave,
  onLiquidTargetMove,
  onLiquidTargetDown,
  onLiquidTargetFocus,
  onLiquidTargetBlur,
  onLiquidTargetKeyDown,
  onLiquidTargetKeyUp,
  ...props
}) {
  const stageRef = useRef(null);
  const activeRef = useRef(active);
  const interactionRef = useRef({ pointer: false, focus: false });
  const isNavigationEffect = variant === "nav" && useSharedNavigationRenderer;
  activeRef.current = active;
  const [interacting, setInteracting] = useState(false);
  const shouldMount = !isNavigationEffect && !disableEffects && (!defer || active || interacting);

  useIsomorphicLayoutEffect(() => {
    if (!isNavigationEffect || disableEffects) return undefined;
    onLiquidStageReady?.(stageRef.current);
    return () => onLiquidStageReady?.(null);
  }, [disableEffects, isNavigationEffect, onLiquidStageReady]);

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
        onPointerEnter={(event) => {
          if (isNavigationEffect) onLiquidTargetEnter?.(stageRef.current, event.nativeEvent);
          else setPointer(true);
          props.onPointerEnter?.(event);
        }}
        onPointerLeave={(event) => {
          if (isNavigationEffect) onLiquidTargetLeave?.(stageRef.current, event.nativeEvent);
          else setPointer(false);
          props.onPointerLeave?.(event);
        }}
        onPointerMove={(event) => {
          if (isNavigationEffect) onLiquidTargetMove?.(stageRef.current, event.nativeEvent);
          props.onPointerMove?.(event);
        }}
        onPointerDown={(event) => {
          if (isNavigationEffect) onLiquidTargetDown?.(stageRef.current, event.nativeEvent);
          else setPointer(true);
          props.onPointerDown?.(event);
        }}
        onFocus={(event) => {
          if (isNavigationEffect) onLiquidTargetFocus?.(stageRef.current, event.nativeEvent);
          else setFocus(true);
          props.onFocus?.(event);
        }}
        onBlur={(event) => {
          if (isNavigationEffect) onLiquidTargetBlur?.(stageRef.current, event.nativeEvent);
          else setFocus(false);
          props.onBlur?.(event);
        }}
        onKeyDown={(event) => {
          if (isNavigationEffect) onLiquidTargetKeyDown?.(stageRef.current, event.nativeEvent);
          props.onKeyDown?.(event);
        }}
        onKeyUp={(event) => {
          if (isNavigationEffect) onLiquidTargetKeyUp?.(stageRef.current, event.nativeEvent);
          props.onKeyUp?.(event);
        }}
      >
        {children}
      </button>
    </span>
  );
}
