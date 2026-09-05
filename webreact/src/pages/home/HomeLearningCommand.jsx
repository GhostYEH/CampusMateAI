import { Suspense, lazy } from "react";
import { useApp } from "../../app/AppContext.jsx";
import { Icon } from "../../components/Icon.jsx";

const ElasticMesh = lazy(() => import("../../components/ElasticMesh.jsx"));

const stages = [
  { key: "observe", label: "观察", detail: "课程 · 任务 · 考试" },
  { key: "analyze", label: "分析", detail: "识别时间与优先级" },
  { key: "plan", label: "计划", detail: "选出当前行动" },
  { key: "execute", label: "执行", detail: "进入现有功能完成" },
];

export default function HomeLearningCommand({ command, onNavigate }) {
  const { reduceMotion } = useApp();
  function navigate(path) { if (path) onNavigate?.(path); }
  return (
    <section className="home-learning-command" aria-labelledby="home-command-title">
      <Suspense fallback={null}>{!reduceMotion && <ElasticMesh className="home-command-mesh" aria-hidden="true" />}</Suspense>
      <div className="command-copy">
        <span className="command-eyebrow"><i />{command.eyebrow}</span>
        <h1 id="home-command-title">{command.headline}</h1>
        <p>{command.detail}</p>
        <div className="command-actions">
          <button className="command-primary" onClick={() => navigate(command.primaryAction.path)}>
            {command.primaryAction.label}
            <Icon name={command.primaryAction.icon} size={17} weight="bold" />
          </button>
          <button className="command-secondary" onClick={() => navigate(command.secondaryAction.path)}>
            <Icon name={command.secondaryAction.icon} size={17} />
            {command.secondaryAction.label}
          </button>
        </div>
        <small className="command-trust"><Icon name="PhShieldCheck" size={15} />建议来自你已同步的校园数据，执行仍由你决定</small>
      </div>
      <aside className="home-agent-loop" aria-label="今日行动形成过程">
        <header><span>行动路径</span><b>Campus Agent</b></header>
        <ol>
          {stages.map((stage, index) => (
            <li key={stage.key} className={index === stages.length - 1 ? "active" : ""}>
              <i>{index + 1}</i>
              <span><strong>{stage.label}</strong><small>{stage.detail}</small></span>
              {index === stages.length - 1 && <Icon name="PhArrowRight" size={15} />}
            </li>
          ))}
        </ol>
      </aside>
    </section>
  );
}
