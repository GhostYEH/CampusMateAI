import { SkeuomorphicToggleCollection } from "@designcodeio/threeui";
import "@designcodeio/threeui/style.css";

import "./SkeuomorphicGlassToggle.css";

export default function SkeuomorphicGlassToggle({ label, value, onChange, className = "" }) {
  return <div className={`skeuomorphic-glass-toggle ${className}`} data-state={value ? "on" : "off"}>
    <SkeuomorphicToggleCollection
      className="skeuomorphic-glass-toggle__scene"
      variant="glass"
      mode="auto"
      defaultOn={value}
      label={label}
      speed={1.00}
      size={1.00}
      opacity={1.00}
      hue={0}
      saturation={1.00}
      brightness={1.00}
      onChange={onChange}
    />
  </div>;
}
