import client from "./api";

export async function getKnowledgeStatus() {
  const { data } = await client.get("/knowledge/status");
  return data;
}

export async function listKnowledgeDocuments() {
  const { data } = await client.get("/knowledge/documents");
  return data;
}

export async function uploadKnowledgeDocument(file, metadata = {}) {
  const form = new FormData();
  form.append("file", file);
  for (const [key, value] of Object.entries(metadata)) {
    if (value !== undefined && value !== null && value !== "") form.append(key, value);
  }
  const { data } = await client.post("/knowledge/documents", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function deleteKnowledgeDocument(documentId) {
  const { data } = await client.delete(`/knowledge/documents/${documentId}`);
  return data;
}

export async function rebuildKnowledgeIndex() {
  const { data } = await client.post("/knowledge/rebuild");
  return data;
}

export async function listUsers(params = {}) {
  const { data } = await client.get("/auth/admin/users", { params: { page_size: 100, ...params } });
  return data;
}

export async function createUser(payload) {
  const { data } = await client.post("/auth/admin/users", payload);
  return data;
}

export async function updateUser(userId, payload) {
  const { data } = await client.patch(`/auth/admin/users/${userId}`, payload);
  return data;
}

export async function getEduDiscoveryStats() {
  const { data } = await client.get("/edu/discovery/stats");
  return data;
}

export async function listEduDiscoveryCandidates(params = {}) {
  const { data } = await client.get("/edu/discovery/candidates", { params });
  return data;
}

export async function reviewEduCandidate(schoolCode, action) {
  const { data } = await client.post(`/edu/discovery/candidates/${schoolCode}/review`, { action });
  return data;
}