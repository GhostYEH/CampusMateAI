export async function streamAssistantSpeech(text, {
  baseUrl = "/api/v1",
  accessToken = "",
  signal,
  onChunk = () => {},
  onHeaders = () => {},
  fetchImpl = globalThis.fetch,
} = {}) {
  const response = await fetchImpl(`${baseUrl}/assistant/tts`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify({ text }),
    signal,
  });
  if (!response.ok) throw new Error(`语音服务错误 (${response.status})`);
  const reader = response.body?.getReader();
  if (!reader) throw new Error("当前浏览器不支持流式语音");
  onHeaders(response.headers);
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    if (value?.byteLength) await onChunk(value);
  }
}
