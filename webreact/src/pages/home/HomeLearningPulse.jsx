import { Icon } from "../../components/Icon.jsx";

export default function HomeLearningPulse({ items, onNavigate }) {
  function navigate(path) { if (path) onNavigate?.(path); }
  return (
    <section className="home-learning-pulse" aria-labelledby="learning-pulse-title">
      <header className="pulse-heading">
        <div><span>今日数据</span><h2 id="learning-pulse-title">校园学习脉搏</h2></div>
        <small>课程、任务、考试与学习记录实时汇合</small>
      </header>
      <div className="pulse-grid">
        {items.map((item) => (
          <button key={item.key} onClick={() => navigate(item.path)}>
            <span className="pulse-icon"><Icon name={item.icon} size={20} /></span>
            <span className="pulse-copy"><small>{item.label}</small><strong>{item.value}</strong><em>{item.detail}</em></span>
            <Icon name="PhArrowUpRight" className="pulse-arrow" size={15} />
          </button>
        ))}
      </div>
    </section>
  );
}