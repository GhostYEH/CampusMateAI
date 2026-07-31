import client from "../api";

export async function listTeacherAnnouncements(params = {}) {
  const { data } = await client.get("/teacher/announcements", {
    params: { page_size: 100, ...params },
  });
  return data;
}

export async function listClassAnnouncements(classId, params = {}) {
  const { data } = await client.get(`/classes/${classId}/announcements`, {
    params: { page_size: 100, ...params },
  });
  return data;
}

export async function getAnnouncement(announcementId) {
  const { data } = await client.get(`/announcements/${announcementId}`);
  return data;
}

export async function createAnnouncement(classId, payload) {
  const { data } = await client.post(`/classes/${classId}/announcements`, payload);
  return data;
}

export async function updateAnnouncement(announcementId, payload) {
  const { data } = await client.patch(`/announcements/${announcementId}`, payload);
  return data;
}

export async function publishAnnouncement(announcementId) {
  const { data } = await client.post(`/announcements/${announcementId}/publish`);
  return data;
}

export async function deleteAnnouncement(announcementId) {
  const { data } = await client.delete(`/announcements/${announcementId}`);
  return data;
}

export async function getReadStatus(announcementId) {
  const { data } = await client.get(`/announcements/${announcementId}/read-status`);
  return data;
}