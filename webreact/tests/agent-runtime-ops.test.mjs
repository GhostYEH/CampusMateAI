import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const root = new URL("../src/", import.meta.url);
const read = (file) => fs.readFileSync(new URL(file, root), "utf8");

/** 断言"不存在某个能力"时必须先剔除注释,否则文档里的说明文字会误伤测试。 */
const stripComments = (source) =>
  source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");

test("管理员观测页按需加载且有路由守卫", () => {
  const app = read("App.jsx");
  const preload = read("app/routePreload.js");
  const page = read("pages/AgentRuntimeOpsPage.jsx");

  assert.match(app, /path="\/admin\/agent-runtime"/);
  assert.match(app, /lazy\(\(\) => import\("\.\/pages\/AgentRuntimeOpsPage\.jsx"\)\)/);
  assert.match(preload, /admin: \(\) => import\("\.\.\/pages\/AgentRuntimeOpsPage\.jsx"\)/);
  // 非管理员必须安全回到首页，而不是渲染运行数据或白屏。
  assert.match(page, /if \(!allowed\) return <Navigate to="\/home" replace \/>/);
  assert.match(page, /canViewAgentOps\(session\)/);
});

test("观测面严格只读：没有写操作入口", () => {
  const page = read("pages/AgentRuntimeOpsPage.jsx");
  const api = read("data/agentObservabilityApi.js");
  const overview = read("components/agentOps/RuntimeOverview.jsx");
  const trace = read("components/agentOps/RunTrace.jsx");

  // API 层只允许 GET，不得出现写动词。
  assert.match(api, /client\.get\("\/admin\/agent-runtime\/overview"/);
  assert.match(api, /client\.get\(`\/admin\/agent-runtime\/runs\//);
  for (const source of [api, page, overview, trace]) {
    const code = stripComments(source);
    assert.doesNotMatch(code, /client\.(post|patch|put|delete)/);
    assert.doesNotMatch(code, /replay\(|重放|改状态|执行工具/);
  }
  // 不得提供查看原始模型内容的入口。
  assert.doesNotMatch(stripComments(trace), /model_response|prompt|raw_arguments/);
});

test("默认不自动高频刷新，轮询可关闭且为 30 秒", () => {
  const page = read("pages/AgentRuntimeOpsPage.jsx");
  assert.match(page, /const AUTO_REFRESH_MS = 30000;/);
  assert.match(page, /useState\(false\)/);
  assert.match(page, /clearInterval\(timer\)/);
  assert.match(page, /每 30 秒自动刷新/);
});

test("概览在空队列/部分失败/审批积压/陈旧租约下均可读且不崩溃", () => {
  const overview = read("components/agentOps/RuntimeOverview.jsx");

  // 空队列与缺样本：显示"暂无样本"，不用 0 伪装健康。
  assert.match(overview, /暂无样本/);
  assert.match(overview, /该时间窗内没有运行记录/);
  assert.match(overview, /queue_depth/);
  // 部分失败与重试、审批积压、陈旧租约都要显式呈现。
  assert.match(overview, /tool_failure_count/);
  assert.match(overview, /retry_count/);
  assert.match(overview, /stale_lease_count/);
  assert.match(overview, /approval\?\.pending/);
  assert.match(overview, /approval\?\.expired/);
  // 未知状态安全降级为只读计数，不解释、不崩溃。
  assert.match(overview, /其他（/);
});

test("时间线对未知事件类型安全降级", () => {
  const trace = read("components/agentOps/RunTrace.jsx");
  assert.match(trace, /events\.map/);
  assert.match(trace, /event\.type/);
  // 事件只按 sequence/type/status 渲染，不解释未知语义。
  assert.match(trace, /event\.sequence/);
  assert.match(trace, /暂无事件/);
});

test("观测 API 只有管理员可访问", () => {
  const api = read("data/agentObservabilityApi.js");
  assert.match(api, /session\.role === "admin"/);
});
