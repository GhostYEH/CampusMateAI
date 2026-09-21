import { client } from "./api.js";

/**
 * 导航栏「学习空间」的服务状态（`GET /magicclass/learning-space/status`）。
 *
 * 学习空间是上游 magic class 应用以**独立进程、独立 Origin** 运行的那一份。
 * CampusMate 不为它做反向代理：浏览器只从后端拿到「是否可用」与「允许内嵌的
 * 公开 Origin」。后端未配置公开 Origin 时 `embed_origin` 为 null —— 调用方据此
 * fail-closed，不渲染 iframe。
 */
export async function getLearningSpaceStatus() {
  const { data } = await client.get("/magicclass/learning-space/status");
  return data;
}
