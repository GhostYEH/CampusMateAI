import React from "react";
import { Button } from "../Primitives.jsx";
import { pblProgress } from "../../features/openmaic/sceneRuntimeModel.js";

function storageKey(sceneId) { return sceneId ? `campusmate:openmaic:pbl:${sceneId}` : ""; }

function savedTasks(sceneId) {
  if (!storageKey(sceneId) || typeof window === "undefined") return [];
  try { return JSON.parse(window.localStorage.getItem(storageKey(sceneId)) || "[]"); } catch { return []; }
}

export default function PblRuntimePanel({ content, sceneId }) {
  const phases = Array.isArray(content?.phases) ? content.phases : [];
  const [completed, setCompleted] = React.useState(() => savedTasks(sceneId));
  const progress = pblProgress(content, completed);

  function toggle(taskId) {
    setCompleted((current) => {
      const next = current.includes(taskId) ? current.filter((id) => id !== taskId) : [...current, taskId];
      if (storageKey(sceneId) && typeof window !== "undefined") window.localStorage.setItem(storageKey(sceneId), JSON.stringify(next));
      return next;
    });
  }

  function reset() {
    setCompleted([]);
    if (storageKey(sceneId) && typeof window !== "undefined") window.localStorage.removeItem(storageKey(sceneId));
  }

  return <section className="openmaic-pbl-runtime" aria-label="项目式学习任务">
    <div className="openmaic-runtime-result">
      <span className="openmaic-runtime-kicker">项目式学习</span>
      <strong>{progress.completed} / {progress.total} 项任务已完成</strong>
      <p>{progress.percent === 100 ? "项目已完成，可以整理并提交你的结论。" : "按阶段完成任务，逐步形成最终交付物。"}</p>
    </div>
    {phases.map((phase, index) => <article className="openmaic-pbl-runtime__phase" key={phase.id || index}>
      <h3>{index + 1}. {phase.title || "项目阶段"}</h3>
      {(Array.isArray(phase.tasks) ? phase.tasks : []).map((task, taskIndex) => <label className="openmaic-pbl-runtime__task" key={task.id || taskIndex}>
        <input type="checkbox" checked={completed.includes(task.id)} onChange={() => toggle(task.id)} />
        <span>{task.title || "完成阶段任务"}</span>
      </label>)}
    </article>)}
    <Button type="button" variant="secondary" onClick={reset}>重置项目进度</Button>
  </section>;
}
