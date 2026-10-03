import "./SkeuomorphicGlassToggle.css";

export default function SkeuomorphicGlassToggle({ label, value, onChange, className = "" }) {
  return <button
    type="button"
    tabIndex={0}
    role="switch"
    aria-label={label}
    aria-checked={Boolean(value)}
    className={`skeuomorphic-glass-toggle ${className}`.trim()}
    data-state={value ? "on" : "off"}
    onClick={() => onChange(!value)}
  >
    <span className="skeuomorphic-glass-toggle__label">{label}</span>
    <span className="skeuomorphic-glass-toggle__track" aria-hidden="true"><span className="skeuomorphic-glass-toggle__thumb" /></span>
    <span className="skeuomorphic-glass-toggle__value" aria-hidden="true">{value ? "开启" : "关闭"}</span>
  </button>;
}
