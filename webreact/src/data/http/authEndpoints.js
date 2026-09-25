import { client, saveTokenPair } from "./client.js";

const dataOf = (response) => response.data;

export async function probeBackend() {
  try { await client.get("/health"); return true; } catch { return false; }
}

export async function login(username, password) {
  const { data } = await client.post("/auth/login", { username, password });
  saveTokenPair(data);
  const profile = dataOf(await client.get("/auth/me"));
  return profile.user || profile;
}

export function getDeviceId(storage = globalThis.localStorage) {
  let id = storage.getItem("campus_device_id");
  if (!id) {
    id = `web_${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
    storage.setItem("campus_device_id", id);
  }
  return id;
}

export async function qrCreate() { return dataOf(await client.post("/auth/qr/create", { device_id: getDeviceId() })); }
export async function qrStatus(sessionId, browserToken) { return dataOf(await client.get(`/auth/qr/${sessionId}/status`, { headers: { "x-browser-token": browserToken } })); }
export async function qrExchange(sessionId, browserToken) { return dataOf(await client.post("/auth/qr/exchange", { session_id: sessionId, browser_token: browserToken })); }
export async function trustedDeviceAutoLogin() {
  const response = await client.post("/auth/trusted-device/auto-login", { device_id: getDeviceId() }, { validateStatus: (status) => status === 200 || status === 401 });
  return response.status === 401 ? null : dataOf(response);
}
export async function revokeTrustedDevice() { try { await client.post("/auth/trusted-device/revoke", {}); } catch { /* a missing cookie is valid */ } }
