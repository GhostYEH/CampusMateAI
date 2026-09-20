/** Resolve the classroom runtime from the learner's natural-language request. */
export function inferHomeGenerationMode(topic) {
  const value = String(topic || "").trim();
  if (/(小组|调研|方案|成果展示|项目式|项目任务|里程碑)/.test(value)) return "pbl";
  if (/(实验|仿真|模拟|变量|数据记录|误差分析|调整参数|观察结果)/.test(value)) return "simulation";
  // A teaching request that also asks for practice must keep its explanatory
  // slides; the service quality gate adds an answerable quiz scene.
  return "slide";
}
