import { Icon } from "../../../components/Icon.jsx";

const locations = [
  { label: "专注训练场", code: "FOCUS", icon: "PhTimer", route: "/study", position: "north-west" },
  { label: "AI 基地", code: "AI BASE", icon: "PhSparkle", route: "/counselor", position: "north-east" },
  { label: "挑战大厅", code: "EXAMS", icon: "PhExam", route: "/exams", position: "south-east" },
];

export default function CampusMap({ onNavigate }) {
  return (
    <section className="rpg-campus-map rpg-hud-panel" aria-labelledby="campus-map-title">
      <header className="rpg-panel-header">
        <div><span className="rpg-kicker">CAMPUS MAP · 6 LOCATIONS</span><h2 id="campus-map-title">校园地图</h2></div>
        <Icon name="PhMapTrifold" size={22} />
      </header>
      <div className="rpg-map-field">
        <div className="rpg-map-core" aria-hidden="true"><Icon name="PhGraduationCap" size={25} weight="duotone" /><small>CAMPUS</small><strong>CORE</strong></div>
        {locations.map((location) => (
          <button key={location.route} className={location.position} onClick={() => onNavigate?.(location.route)}>
            <span><Icon name={location.icon} size={19} /></span>
            <strong>{location.label}</strong>
            <small>{location.code}</small>
          </button>
        ))}
      </div>
    </section>
  );
}
