import { client } from "./api.js";

/**
 * 课堂 AI 同学的浏览器接口。
 *
 * 人设、模型与凭据都留在后端；这里只传当前页与记忆，响应里的 `usage.tokens`
 * 由调用方累计到预算。
 */
export async function getClassmateRoster() {
  const { data } = await client.get("/magicclass/classmates/roster");
  return data;
}

export async function getClassmateBudget() {
  const { data } = await client.get("/magicclass/classmates/budget");
  return data;
}

export async function respondClassmates({ courseId, scene, memory, language = "zh-CN" }) {
  const { data } = await client.post("/magicclass/classmates/respond", {
    course_id: courseId,
    scene,
    memory,
    language,
  }, { timeout: 65_000 });
  return data;
}

export async function askClassmate({ courseId, scene, memory, agentId, question, language = "zh-CN" }) {
  const { data } = await client.post("/magicclass/classmates/ask", {
    course_id: courseId,
    scene,
    memory,
    agentId,
    question,
    language,
  }, { timeout: 50_000 });
  return data;
}
