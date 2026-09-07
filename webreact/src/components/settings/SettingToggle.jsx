import SkeuomorphicGlassToggle from "./SkeuomorphicGlassToggle.jsx";

export default function SettingToggle({ label, detail, value, onChange }) {
  return <div className="settings-option">
    <div className="settings-option-copy"><strong>{label}</strong><small>{detail}</small></div>
    <div className="settings-toggle settings-toggle-shell" aria-pressed={value}>
      <SkeuomorphicGlassToggle label={label} value={value} onChange={onChange} />
    </div>
  </div>;
}
