import client from "../api";

export async function listTeacherAssignments(params = {}) {
  const { data } = await client.get("/teacher/assignments", {
    params: { page_size: 100, ...params },
  });
  return data;
}

export async function listClassAssignments(classId, params = {}) {
  const { data } = await client.get(`/classes/${classId}/assignments`, {
    params: { page_size: 100, ...params },
  });
  return data;
}

export async function getAssignment(assignmentId) {
  const { data } = await client.get(`/assignments/${assignmentId}`);
  return data;
}

export async function createAssignment(classId, payload) {
  const { data } = await client.post(`/classes/${classId}/assignments`, payload);
  return data;
}

export async function updateAssignment(assignmentId, payload) {
  const { data } = await client.patch(`/assignments/${assignmentId}`, payload);
  return data;
}

export async function publishAssignment(assignmentId) {
  const { data } = await client.post(`/assignments/${assignmentId}/publish`);
  return data;
}

export async function closeAssignment(assignmentId) {
  const { data } = await client.post(`/assignments/${assignmentId}/close`);
  return data;
}

export async function archiveAssignment(assignmentId) {
  const { data } = await client.patch(`/assignments/${assignmentId}`, {
    status: "archived",
  });
  return data;
}

export async function getAssignmentStats(assignmentId) {
  const { data } = await client.get(`/assignments/${assignmentId}/stats`);
  return data;
}

export async function getStudentStatus(assignmentId, params = {}) {
  const { data } = await client.get(`/assignments/${assignmentId}/student-status`, {
    params: { page_size: 200, ...params },
  });
  return data;
}

export async function uploadAssignmentAttachment(assignmentId, file, onProgress) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await client.post(
    `/assignments/${assignmentId}/attachments`,
    formData,
    {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: onProgress
        ? (event) => onProgress(Math.round((event.loaded * 100) / (event.total || file.size)))
        : undefined,
    },
  );
  return data;
}

export async function listAssignmentAttachments(assignmentId) {
  const { data } = await client.get(`/assignments/${assignmentId}/attachments`);
  return data;
}

export function buildAttachmentDownloadUrl(assignmentId, attachmentId) {
  const base = client.defaults.baseURL;
  const token = localStorage.getItem("campus_access_token");
  return `${base}/assignments/${assignmentId}/attachments/${attachmentId}?access_token=${encodeURIComponent(token || "")}`;
}