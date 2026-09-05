import { Icon } from "../Icon.jsx";

export default function SettingToggle({ label, detail, value, onChange }) {
  return <div className="settings-option">
    <div className="settings-option-copy"><strong>{label}</strong><small>{detail}</small></div>
    <button type="button" className={`settings-toggle ${value ? "is-on" : ""}`} role="switch" aria-checked={value} aria-pressed={value} aria-label={`${label}，${value ? "已开启" : "已关闭"}`} onClick={() => onChange(!value)}>
      <span className="settings-toggle-track"><i /></span><span className="settings-toggle-state">{value ? <><Icon name="PhCheck" size={13} weight="bold" />已开启</> : "已关闭"}</span>
    </button>
  </div>;
}
