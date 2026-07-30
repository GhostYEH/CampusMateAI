import axios from "axios";
const client = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1", timeout: 8000 });
client.interceptors.request.use((config) => {
  const token = localStorage.getItem("campus_access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
export async function probeBackend() { try { await client.get("/health"); return true; } catch { return false; } }
export async function realLogin(username, password) {
  const { data } = await client.post("/auth/login", { username, password });
  localStorage.setItem("campus_access_token", data.access_token);
  localStorage.setItem("campus_refresh_token", data.refresh_token);
  const me = await client.get("/auth/me");
  return me.data.user || me.data;
}
export async function chat(message) { const { data } = await client.post("/counselor/chat", { message, session_id: "web-session" }); return data; }
export async function extractNotice(text) { const { data } = await client.post("/notices/extract-multi", { text }); return data; }
export default client;
