import client from "../api";

export async function listTeacherSubmissions(params = {}) {
  const { data } = await client.get("/teacher/submissions", {
    params: { page_size: 100, ...params },
  });
  return data;
}

export async function listAssignmentSubmissions(assignmentId, params = {}) {
  const { data } = await client.get(`/assignments/${assignmentId}/submissions`, {
    params: { page_size: 200, ...params },
  });
  return data;
}

export async function getSubmission(submissionId) {
  const { data } = await client.get(`/submissions/${submissionId}`);
  return data;
}

export async function gradeSubmission(submissionId, payload) {
  const { data } = await client.post(`/submissions/${submissionId}/grade`, payload);
  return data;
}

export function buildSubmissionAttachmentDownloadUrl(submissionId, attachmentId) {
  const base = client.defaults.baseURL;
  const token = localStorage.getItem("campus_access_token");
  return `${base}/submissions/${submissionId}/attachments/${attachmentId}?access_token=${encodeURIComponent(token || "")}`;
}