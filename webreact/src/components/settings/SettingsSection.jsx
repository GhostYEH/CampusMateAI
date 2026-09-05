import { Icon } from "../Icon.jsx";

export default function SettingsSection({ icon, tone = "blue", title, detail, className = "", children }) {
  return <section className={`settings-section settings-${tone} ${className}`}>
    <header className="settings-section-heading">
      <span className="settings-section-icon"><Icon name={icon} size={20} weight="duotone" /></span>
      <div><h2>{title}</h2><p>{detail}</p></div>
    </header>
    <div className="settings-section-body">{children}</div>
  </section>;
}
