import { useEffect, useRef } from "react";
import { mountLiquidMetal } from "./liquidMetalScene";

function stageModifier(className) {
  if (className.includes("sylva-priority-more")) return "sylva-liquid-stage--wide";
  if (className.includes("sylva-card-link")) return "sylva-liquid-stage--compact";
  return "sylva-liquid-stage--overview";
}

export default function LiquidMetalButton({ children, className = "", ...props }) {
  const stageRef = useRef(null);

  useEffect(() => mountLiquidMetal(stageRef.current), []);

  return (
    <span
      ref={stageRef}
      className={`sylva-liquid-stage ${stageModifier(className)}`}
      data-liquid-metal="explore"
    >
      <span className="sylva-liquid-plate" aria-hidden="true" />
      <canvas className="sylva-liquid-fx" aria-hidden="true" />
      <button
        type="button"
        className={`sylva-liquid-control ${className}`.trim()}
        {...props}
      >
        {children}
      </button>
    </span>
  );
}
