import client from "../api";

export async function listClasses(params = {}) {
  const { data } = await client.get("/classes", {
    params: { page_size: 100, ...params },
  });
  return data;
}

export async function createClass(courseId, payload) {
  const { data } = await client.post(`/courses/${courseId}/classes`, payload);
  return data;
}

export async function updateClass(classId, payload) {
  const { data } = await client.patch(`/classes/${classId}`, payload);
  return data;
}

export async function resetInviteCode(classId) {
  const { data } = await client.post(`/classes/${classId}/reset-invite-code`);
  return data;
}

export async function listMembers(classId, params = {}) {
  const { data } = await client.get(`/classes/${classId}/members`, {
    params: { page_size: 200, ...params },
  });
  return data;
}

export async function removeMember(classId, userId) {
  const { data } = await client.delete(`/classes/${classId}/members/${userId}`);
  return data;
}