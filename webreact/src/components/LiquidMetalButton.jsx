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
  defer = false,
  ...props
}) {
  const stageRef = useRef(null);
  const activeRef = useRef(active);
  activeRef.current = active;
  const [interacting, setInteracting] = useState(false);
  const shouldMount = !defer || active || interacting;

  useEffect(() => {
    if (!shouldMount) return undefined;
    return mountLiquidMetal(stageRef.current, { getActive: () => activeRef.current });
  }, [shouldMount]);

  const wake = () => { if (defer) setInteracting(true); };
  const release = () => { if (defer && !activeRef.current) setInteracting(false); };

  return (
    <span
      ref={stageRef}
      className={`sylva-liquid-stage ${stageModifier(className, variant)}`}
      data-liquid-metal="explore"
      data-active={active ? "true" : undefined}
    >
      {shouldMount && <span className="sylva-liquid-plate" aria-hidden="true" />}
      {shouldMount && <canvas className="sylva-liquid-fx" aria-hidden="true" />}
      <button
        type="button"
        className={`sylva-liquid-control ${className}`.trim()}
        {...props}
        onPointerEnter={(event) => { wake(); props.onPointerEnter?.(event); }}
        onPointerLeave={(event) => { release(); props.onPointerLeave?.(event); }}
        onFocus={(event) => { wake(); props.onFocus?.(event); }}
        onBlur={(event) => { release(); props.onBlur?.(event); }}
      >
        {children}
      </button>
    </span>
  );
}
