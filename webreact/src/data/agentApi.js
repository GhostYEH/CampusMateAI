import { BASE_URL, client } from "./api.js";

const data = (response) => response.data;
const requestId = () => globalThis.crypto?.randomUUID?.() || `agent-${Date.now()}-${Math.random().toString(16).slice(2)}`;

export const agentApi = {
  listCampaigns: async () => data(await client.get("/final-review/campaigns")),
  createCampaign: async (payload) => data(await client.post("/final-review/campaigns", payload)),
  generatePlan: async (id) => data(await client.post(`/final-review/campaigns/${id}/plans/generate`)),
  activatePlan: async (id) => data(await client.post(`/final-review/campaigns/${id}/activate`)),
  todayAgenda: async (id) => data(await client.get(`/final-review/campaigns/${id}/agendas/today`)),
  completeDailyItem: async (id) => data(await client.post(`/final-review/daily-items/${id}/complete`)),
  createResearch: async (payload, key = requestId()) => data(await client.post("/course-research/sessions", payload, { headers: { "Idempotency-Key": key } })),
  createManualNotice: async (payload) => data(await client.post("/notices/manual", payload)),
  analyzeNotice: async (id) => data(await client.post(`/notices/${id}/workflow`)),
  confirmNotice: async (id, approved) => data(await client.post(`/notice-workflows/${id}/confirm`, { approved })),
  executeNotice: async (id, idempotencyKey = requestId()) => data(await client.post(`/notice-workflows/${id}/execute`, { idempotency_key: idempotencyKey })),
};

export function createAgentEventStream(runId, { token, lastEventId, onEvent, onError, signal } = {}) {
  const headers = { Accept: "text/event-stream" };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (lastEventId) headers["Last-Event-ID"] = lastEventId;
  return fetch(`${BASE_URL}/agent-runs/${encodeURIComponent(runId)}/events/stream`, { headers, signal })
    .then(async (response) => {
      if (!response.ok || !response.body) throw new Error("智能体事件流连接失败");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split("\n\n");
        buffer = frames.pop() || "";
        frames.forEach((frame) => {
          const id = frame.match(/^id:\s*(.+)$/m)?.[1];
          const raw = frame.match(/^data:\s*(.+)$/m)?.[1];
          if (raw) onEvent?.({ id, data: JSON.parse(raw) });
        });
      }
    }).catch((error) => { if (error.name !== "AbortError") onError?.(error); });
}

export function reduceAgentEvents(events, incoming) {
  if (!incoming?.data?.sequence || events.some((item) => item.data.sequence === incoming.data.sequence)) return events;
  return [...events, incoming].sort((a, b) => a.data.sequence - b.data.sequence);
}
