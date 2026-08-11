import client from "../api";

const BASE_URL = client.defaults.baseURL;

/**
 * 流式 AI 教学助理对话 — 支持课程/班级/作业/通知上下文。
 *
 * @param {string} message          用户问题
 * @param {object} context          上下文 { course_id, class_id, assignment_id, announcement_id }
 * @param {object} callbacks        { onSources, onChunk, onDone, onError, signal }
 */
export async function teacherChatStream(message, context = {}, { onSources, onChunk, onDone, onError, signal } = {}) {
  const token = localStorage.getItem("campus_access_token");
  try {
    const resp = await fetch(`${BASE_URL}/counselor/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        message,
        stream: true,
        course_id: context.course_id || null,
        class_id: context.class_id || null,
        assignment_id: context.assignment_id || null,
        announcement_id: context.announcement_id || null,
      }),
      signal,
    });

    if (!resp.ok) {
      const body = await resp.text().catch(() => "");
      onError?.(new Error(`服务器错误 (${resp.status}): ${body.slice(0, 120)}`));
      return;
    }

    const reader = resp.body?.getReader();
    if (!reader) {
      onError?.(new Error("浏览器不支持流式读取"));
      return;
    }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";
      for (const block of parts) {
        if (!block.trim()) continue;
        const lines = block.split("\n");
        let eventType = "";
        let dataStr = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) eventType = line.slice(7).trim();
          else if (line.startsWith("data: ")) dataStr = line.slice(6);
        }
        if (!dataStr) continue;
        try {
          const data = JSON.parse(dataStr);
          if (eventType === "sources") onSources?.(data.sources || []);
          else if (eventType === "chunk") onChunk?.(data.text || "", data.mode || "llm");
          else if (eventType === "done") onDone?.(data);
          else if (eventType === "error") onError?.(new Error(data.message || "未知错误"));
        } catch { /* skip */ }
      }
    }
  } catch (err) {
    if (err.name === "AbortError") return;
    onError?.(err);
  }
}

export async function teacherChat(message, context = {}) {
  const { data } = await client.post("/counselor/chat", {
    message,
    stream: false,
    course_id: context.course_id || null,
    class_id: context.class_id || null,
    assignment_id: context.assignment_id || null,
    announcement_id: context.announcement_id || null,
  });
  return data;
}