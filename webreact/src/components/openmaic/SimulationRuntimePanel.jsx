import React from "react";
import { Button } from "../Primitives.jsx";
import { createSimulationState, stepSimulation } from "../../features/openmaic/sceneRuntimeModel.js";

export default function SimulationRuntimePanel({ content, sceneId }) {
  const [state, setState] = React.useState(() => createSimulationState(content));
  const parameters = Array.isArray(content?.widgetConfig?.parameters) ? content.widgetConfig.parameters : [];
  const title = content?.widgetConfig?.title || "互动实验";

  function update(id, value) { setState((current) => stepSimulation(content, current, { type: "set", id, value })); }
  function run() { setState((current) => stepSimulation(content, current, { type: "run" })); }
  function reset() { setState(() => createSimulationState(content)); }

  return <section className="openmaic-simulation-runtime" aria-label={`${title}实验`} data-scene-id={sceneId || undefined}>
    <div className="openmaic-runtime-cover">
      <span className="openmaic-runtime-kicker">互动实验</span>
      <strong>{title}</strong>
      <p>调整参数，运行实验，观察结果变化。</p>
    </div>
    <div className="openmaic-simulation-runtime__controls" aria-label="实验参数">
      {parameters.map((parameter) => <label className="openmaic-simulation-runtime__control" key={parameter.id}>
        <span>{parameter.label || parameter.id}</span>
        <input
          type="range"
          min={parameter.min}
          max={parameter.max}
          step={parameter.step || 1}
          value={state.values[parameter.id] ?? parameter.value ?? parameter.min ?? 0}
          onChange={(event) => update(parameter.id, event.target.value)}
          aria-label={parameter.label || parameter.id}
        />
        <span className="openmaic-simulation-runtime__value">{state.values[parameter.id]} {parameter.unit || ""}</span>
      </label>)}
    </div>
    <div className="openmaic-stage-heading-actions">
      <Button type="button" onClick={run}>运行实验</Button>
      <Button type="button" variant="secondary" onClick={reset}>重置实验</Button>
    </div>
    {state.hasRun && state.result ? <div className="openmaic-simulation-runtime__result" role="status" aria-label="实验结果">
      <span>{state.result.label}</span>
      <strong>{state.result.value}</strong>
      <small>根据当前参数计算得到</small>
    </div> : <p className="openmaic-hint">调整参数后点击“运行实验”查看结果。</p>}
  </section>;
}
