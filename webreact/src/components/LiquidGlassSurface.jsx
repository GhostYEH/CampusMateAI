import { forwardRef } from "react";
import "./LiquidGlassSurface.css";

const LiquidGlassSurface = forwardRef(function LiquidGlassSurface({ children, className = "", style = {} }, ref) {
  return (
    <div ref={ref} className={`liquid-glass-surface ${className}`} style={style}>
      <span className="liquid-glass-surface__sheen" aria-hidden="true" />
      <div className="liquid-glass-surface__content">{children}</div>
    </div>
  );
});

export default LiquidGlassSurface;
