import client from "../api";

export async function getChaoxingStatus() {
  const { data } = await client.get("/chaoxing/status");
  return data;
}

export async function loginChaoxing(username, password) {
  const { data } = await client.post("/chaoxing/login", { username, password }, { timeout: 30000 });
  return data;
}

export async function syncChaoxing() {
  const { data } = await client.post("/chaoxing/sync", {}, { timeout: 120000 });
  return data;
}

export async function disconnectChaoxing() {
  const { data } = await client.post("/chaoxing/disconnect");
  return data;
}