import client from "./api";

export async function getAdminOverview() {
  const { data } = await client.get("/admin/overview");
  return data;
}

export async function getAdminSystemStatus() {
  const { data } = await client.get("/admin/system/status");
  return data;
}

export async function getAdminUsers(params = {}) {
  const { data } = await client.get("/auth/admin/users", { params: { page: 1, page_size: 20, ...params } });
  return data;
}

export async function createAdminUser(payload) {
  const { data } = await client.post("/auth/admin/users", payload);
  return data;
}

export async function updateAdminUser(id, payload) {
  const { data } = await client.patch(`/auth/admin/users/${id}`, payload);
  return data;
}
export async function getAdminUser(id) { const { data } = await client.get(`/admin/users/${id}`); return data; }
export async function resetAdminPassword(id, password) { const { data } = await client.post(`/admin/users/${id}/reset-password`, { password }); return data; }
export async function getAdminCourses(params = {}) { const { data } = await client.get("/courses", { params: { page: 1, page_size: 20, ...params } }); return data; }
export async function getAdminCourse(id) { const { data } = await client.get(`/courses/${id}`); return data; }
export async function getAdminClasses(params = {}) { const { data } = await client.get("/classes", { params: { page: 1, page_size: 50, ...params } }); return data; }
export async function getAdminClassMembers(id, params = {}) { const { data } = await client.get(`/classes/${id}/members`, { params }); return data; }
export async function createAdminCourse(payload) { const { data } = await client.post("/courses", payload); return data; }
export async function updateAdminCourse(id, payload) { const { data } = await client.patch(`/courses/${id}`, payload); return data; }
export async function getKnowledgeDocuments() { const { data } = await client.get("/knowledge/documents"); return data; }
export async function uploadKnowledgeDocument(file, metadata = {}) { const body = new FormData(); body.append("file", file); Object.entries(metadata).forEach(([k,v]) => v != null && body.append(k, v)); const { data } = await client.post("/knowledge/documents", body); return data; }
export async function deleteKnowledgeDocument(id) { const { data } = await client.delete(`/knowledge/documents/${id}`); return data; }
export async function rebuildKnowledge() { const { data } = await client.post("/knowledge/rebuild"); return data; }
export async function getAuditLogs(params = {}) { const { data } = await client.get("/admin/audit-logs", { params: { page: 1, page_size: 20, ...params } }); return data; }
export async function globalAdminSearch(q) { const { data } = await client.get("/admin/search", { params: { q } }); return data; }
export async function updateAdminProfile(payload) { const { data } = await client.patch("/admin/profile", payload); return data; }

export async function getAdminActivities(params = {}) {
  const { data } = await client.get("/activities", { params: { page: 1, page_size: 20, ...params } });
  return data;
}

export async function createAdminActivity(payload) {
  const { data } = await client.post("/admin/activities", payload);
  return data;
}

export async function updateAdminActivityStatus(id, status) {
  const action = status === "published" ? "publish" : status === "closed" ? "close" : null;
  if (!action) throw new Error("暂不支持该状态操作");
  const { data } = await client.post(`/admin/activities/${id}/${action}`);
  return data;
}
