import axios from "axios";
import { itemsOf, studySessionPayload } from "./contracts.js";

const viteEnv = import.meta.env || {};
export const BASE_URL = viteEnv.VITE_API_BASE_URL || "/api/v1";

function storageOrDefault(storage) {
  return storage || globalThis.localStorage;
}

export function createClient(baseUrl = BASE_URL, storage = globalThis.localStorage) {
  const client = axios.create({ baseURL: baseUrl, timeout: 8000, withCredentials: true });
  client.interceptors.request.use((config) => {
    const token = storageOrDefault(storage)?.getItem("campus_access_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  });

  let refreshPromise = null;
  client.interceptors.response.use((response) => response, async (error) => {
    const original = error.config;
    const url = original?.url || "";
    const detail = error.response?.data?.detail;
    const chaoxingAuthError = url.includes("/chaoxing/") && (
      detail === "reauth_required" || detail === "Chaoxing credentials not found"
      || (typeof detail === "string" && detail.startsWith("Chaoxing login failed:"))
    );
    if (error.response?.status !== 401 || !original || original._retried || chaoxingAuthError
      || url.includes("/auth/login") || url.includes("/auth/refresh")) return Promise.reject(error);

    original._retried = true;
    try {
      refreshPromise ||= refreshAccessToken(baseUrl, storageOrDefault(storage));
      const token = await refreshPromise;
      refreshPromise = null;
      original.headers.Authorization = `Bearer ${token}`;
      return client(original);
    } catch (refreshError) {
      refreshPromise = null;
      return Promise.reject(refreshError);
    }
  });
  return client;
}

async function refreshAccessToken(baseUrl, storage) {
  const refreshToken = storage.getItem("campus_refresh_token");
  if (!refreshToken) {
    clearAuth(storage);
    redirectToLogin();
    throw new Error("登录已过期，请重新登录");
  }
  try {
    const { data } = await axios.post(`${baseUrl}/auth/refresh`, { refresh_token: refreshToken });
    storage.setItem("campus_access_token", data.access_token);
    storage.setItem("campus_refresh_token", data.refresh_token);
    return data.access_token;
  } catch {
    clearAuth(storage);
    redirectToLogin();
    throw new Error("登录已过期，请重新登录");
  }
}

function clearAuth(storage = globalThis.localStorage) {
  ["campus_access_token", "campus_refresh_token", "campus_session"].forEach((key) => storage?.removeItem(key));
}

function redirectToLogin() {
  if (typeof location !== "undefined" && location.pathname !== "/login") location.href = "/login";
}

const client = createClient();
const dataOf = (response) => response.data;

export function saveTokenPair(data, storage = globalThis.localStorage) {
  storage.setItem("campus_access_token", data.access_token);
  storage.setItem("campus_refresh_token", data.refresh_token);
}

export const applyTokenPair = saveTokenPair;

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
export async function trustedDeviceAutoLogin() { return dataOf(await client.post("/auth/trusted-device/auto-login", { device_id: getDeviceId() })); }
export async function revokeTrustedDevice() { try { await client.post("/auth/trusted-device/revoke", {}); } catch { /* a missing cookie is valid */ } }

export async function getDashboard() { return dataOf(await client.get("/dashboard/student")); }
export async function getCourses(params = {}) { return dataOf(await client.get("/courses", { params: { page_size: 100, ...params } })); }
export async function getClasses(courseId) { return dataOf(await client.get("/classes", { params: { page_size: 100, ...(courseId ? { course_id: courseId } : {}) } })); }

export async function getCourseDetail(courseId) {
  const [course, classes, summary, content] = await Promise.all([
    client.get(`/courses/${courseId}`),
    getClasses(courseId),
    client.get(`/courses/${courseId}/content-summary`).catch(() => ({ data: null })),
    client.get(`/courses/${courseId}/content`, { params: { page_size: 500 } }).catch(() => ({ data: { items: [] } })),
  ]);
  const classItems = itemsOf(classes);
  const grouped = await Promise.all(classItems.map(async (item) => {
    const [assignments, announcements] = await Promise.all([
      client.get(`/classes/${item.id}/assignments`, { params: { page_size: 100 } }),
      client.get(`/classes/${item.id}/announcements`, { params: { page_size: 100 } }),
    ]);
    return { ...item, assignments: itemsOf(assignments.data), announcements: itemsOf(announcements.data) };
  }));
  return { course: course.data, classes: grouped, contentSummary: summary.data, remoteContent: itemsOf(content.data) };
}

export async function syncCourse(courseId) { return dataOf(await client.post(`/courses/${courseId}/sync`)); }
export async function openCourseResource(courseId, itemId) { return dataOf(await client.get(`/courses/${courseId}/resources/${itemId}/open`)); }
export async function downloadCourseResource(courseId, itemId, filename = "课程资料") {
  const response = await client.get(`/courses/${courseId}/resources/${itemId}/download`, { responseType: "blob" });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || response.headers["content-disposition"] || "课程资料";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function getAssignments(params = {}) { return dataOf(await client.get("/student/assignments", { params: { page_size: 100, ...params } })); }
export async function getTasks(params = {}) { return dataOf(await client.get("/tasks", { params: { page_size: 100, ...params } })); }
export async function rankTasks(taskIds = null) { return dataOf(await client.post("/tasks/rank-importance", taskIds ? { task_ids: taskIds } : {})); }
export async function getNotices(params = {}) { return dataOf(await client.get("/notices", { params: { page_size: 200, ...params } })); }
export async function getTask(id) { return dataOf(await client.get(`/tasks/${id}`)); }
export async function createTask(payload) { return dataOf(await client.post("/tasks", payload)); }
export async function analyzeTaskImport(payload) { return dataOf(await client.post("/tasks/import/analyze", payload)); }
export async function commitTaskImport(payload) { return dataOf(await client.post("/tasks/import/commit", payload)); }
export async function updateTask(id, payload) { return dataOf(await client.patch(`/tasks/${id}`, payload)); }
export async function completeTask(id, completed = true) { return dataOf(await client.post(`/tasks/${id}/${completed ? "complete" : "restore"}`)); }
export async function deleteTask(id) { return dataOf(await client.delete(`/tasks/${id}`)); }
export async function getAssignment(id) { return dataOf(await client.get(`/assignments/${id}`)); }
export async function getSubmission(id) { try { return dataOf(await client.get(`/assignments/${id}/my-submission`)); } catch (error) { if (error.response?.status === 404) return null; throw error; } }
export async function saveSubmission(id, payload) { return dataOf(await client.post(`/assignments/${id}/submissions`, payload)); }
export async function submitSubmission(id) { return dataOf(await client.post(`/submissions/${id}/submit`)); }

export async function getActivities(params = {}) { return dataOf(await client.get("/activities", { params: { page_size: 100, ...params } })); }
export async function getActivity(id) { return dataOf(await client.get(`/activities/${id}`)); }
export async function getActivityRegistration(id) { return dataOf(await client.get(`/activities/${id}/registration`)); }
export async function registerActivity(id) { return dataOf(await client.post(`/activities/${id}/registration`)); }
export async function cancelActivityRegistration(id) { return dataOf(await client.delete(`/activities/${id}/registration`)); }
export async function getAnnouncement(id) { return dataOf(await client.get(`/announcements/${id}`)); }
export async function markAnnouncementRead(id) { return dataOf(await client.post(`/announcements/${id}/read`)); }
export async function getProfile() { const data = dataOf(await client.get("/auth/me")); return data.user || data; }
export async function updateProfile(payload) { return dataOf(await client.patch("/admin/profile", payload)); }

export async function getStudySessions(params = {}) { return itemsOf(dataOf(await client.get("/study/sessions", { params: { page_size: 100, ...params } }))); }
export async function getActiveStudySession() { return dataOf(await client.get("/study/sessions/active")); }
export async function startStudySession(payload) { return dataOf(await client.post("/study/sessions", studySessionPayload(payload))); }
export async function pauseStudySession(id, reason) { return dataOf(await client.post(`/study/sessions/${id}/pause`, null, { params: reason ? { reason } : {} })); }
export async function resumeStudySession(id) { return dataOf(await client.post(`/study/sessions/${id}/resume`)); }
export async function finishStudySession(id, payload = {}) { return dataOf(await client.post(`/study/sessions/${id}/finish`, payload)); }
export async function breakdownStudyTask(payload) { return dataOf(await client.post("/study/task-breakdown", payload)); }

export async function getExams(params = {}) { return itemsOf(dataOf(await client.get("/student/exams", { params }))); }
export async function saveExam(payload, id) { return dataOf(await (id ? client.patch(`/student/exams/${id}`, payload) : client.post("/student/exams", payload))); }
export async function deleteExam(id) { return dataOf(await client.delete(`/student/exams/${id}`)); }
export async function getUniversities(params = {}) { return dataOf(await client.get("/universities", { params })); }
export async function selectUniversity(id) { return dataOf(await client.put("/profile/university", { university_id: id })); }

export async function getCommunityPosts(params = {}) { return dataOf(await client.get("/community/posts", { params })); }
export async function getCommunityCategories() { return dataOf(await client.get("/community/posts/categories")); }
export async function getCommunityPost(id) { return dataOf(await client.get(`/community/posts/${id}`)); }
export async function createCommunityPost(payload) { return dataOf(await client.post("/community/posts", payload)); }
export async function updateCommunityPost(id, payload) { return dataOf(await client.put(`/community/posts/${id}`, payload)); }
export async function deleteCommunityPost(id) { return dataOf(await client.delete(`/community/posts/${id}`)); }
export async function likePost(id) { return dataOf(await client.post(`/community/posts/${id}/like`)); }
export async function unlikePost(id) { return dataOf(await client.delete(`/community/posts/${id}/like`)); }
export async function favoritePost(id) { return dataOf(await client.post(`/community/posts/${id}/favorite`)); }
export async function unfavoritePost(id) { return dataOf(await client.delete(`/community/posts/${id}/favorite`)); }
export async function getComments(id) { return dataOf(await client.get(`/community/posts/${id}/comments`)); }
export async function createComment(id, payload) { return dataOf(await client.post(`/community/posts/${id}/comments`, payload)); }
export async function reportPost(payload) { return dataOf(await client.post("/community/reports", { target_type: "post", target_id: payload.target_id || payload.post_id, reason: payload.reason === "其他" ? "其它" : payload.reason, details: payload.details })); }
export async function uploadCommunityImage(file) {
  const form = new FormData();
  form.append("image", file);
  return dataOf(await client.post("/community/upload-image", form, { headers: { "Content-Type": "multipart/form-data" } }));
}

export function resolveAssetUrl(url) {
  if (!url || /^(https?:|data:)/.test(url)) return url;
  if (url.startsWith("/static/") && BASE_URL.startsWith("http")) {
    try { return new URL(BASE_URL).origin + url; } catch { return url; }
  }
  return url;
}

export async function getAcademicStatus() { return dataOf(await client.get("/academic/status")); }
export async function getAcademicProviders() { return dataOf(await client.get("/academic/providers")); }
export async function getEduBinding() { return dataOf(await client.get("/edu/binding")); }
export async function bindEdu(username, password, systemType = "undergrad") { return dataOf(await client.post("/edu/bind", { username, password, system_type: systemType })); }
export async function unbindEdu() { return dataOf(await client.delete("/edu/binding")); }
export async function syncEdu(type, params = {}) { return dataOf(await client.post(`/edu/sync/${type}`, null, { params })); }
export async function getEduSyncRecords(limit = 20) { return dataOf(await client.get("/edu/sync/records", { params: { limit } })); }
export async function submitEduUrl(url) { const status = await getAcademicStatus().catch(() => ({})); return dataOf(await client.post("/edu/discovery/submit-url", { university_id: status.university_id || "", candidate_url: url })); }
export async function probeEduPortal(url) { return dataOf(await client.post("/edu/discovery/probe", { portal_url: url })); }
export async function createEduConnection(url, universityId = null) { return dataOf(await client.post("/edu/connections/from-url", { portal_url: url, ...(universityId ? { university_id: universityId } : {}) })); }
export async function getEduConnection(id) { return dataOf(await client.get(`/edu/connections/${id}`)); }
export async function continueEduConnection(id, payload) { return dataOf(await client.post(`/edu/connections/${id}/continue`, payload)); }
export async function pollEduConnection(id) { return continueEduConnection(id, { action: "POLL" }); }
export async function preLoginEdu(id) { return dataOf(await client.post(`/edu/connections/${id}/pre-login`, {})); }
export async function getScheduleItems(semester = null) { return dataOf(await client.get("/edu/schedule/items", { params: semester ? { semester } : {} })); }
export async function getGradeItems(semester = null) { return dataOf(await client.get("/edu/grade/items", { params: semester ? { semester } : {} })); }
export async function getExamItems(semester = null) { return dataOf(await client.get("/edu/exam/items", { params: semester ? { semester } : {} })); }

export async function getChaoxingStatus() { return dataOf(await client.get("/chaoxing/status")); }
export async function loginChaoxing(username, password) {
  return dataOf(await client.post("/chaoxing/login", { username, password }, { timeout: 30000 }));
}
export async function syncChaoxing() { return dataOf(await client.post("/chaoxing/sync", {}, { timeout: 120000 })); }
export async function disconnectChaoxing() { return dataOf(await client.post("/chaoxing/disconnect")); }

export async function chatStream(message, { onSources, onChunk, onDone, onError, signal, webSearch = false, attachment = null, conversationId = null, recentTasks = [] } = {}) {
  try {
    const token = localStorage.getItem("campus_access_token");
    const response = await fetch(`${BASE_URL}/counselor/chat`, {
      method: "POST", headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({ message, stream: true, web_search: webSearch, attachment, recent_tasks: recentTasks, ...(conversationId ? { conversation_id: conversationId } : {}) }), signal,
    });
    if (!response.ok) throw new Error(`服务器错误 (${response.status})`);
    const reader = response.body?.getReader();
    if (!reader) throw new Error("浏览器不支持流式读取");
    const decoder = new TextDecoder();
    let buffer = "";
    const consume = (block) => {
      let type = "";
      let dataText = "";
      block.split("\n").forEach((line) => { if (line.startsWith("event: ")) type = line.slice(7).trim(); else if (line.startsWith("data: ")) dataText = line.slice(6); });
      if (!dataText) return;
      try {
        const data = JSON.parse(dataText);
        if (type === "sources") onSources?.(data.sources || []);
        else if (type === "chunk") onChunk?.(data.text || "", data.mode || "llm");
        else if (type === "done") onDone?.(data);
        else if (type === "error") onError?.(new Error(data.message || "未知错误"));
      } catch { /* incomplete SSE payloads are ignored */ }
    };
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() || "";
      blocks.filter(Boolean).forEach(consume);
    }
    if (buffer.trim()) consume(buffer);
  } catch (error) {
    if (error.name !== "AbortError") onError?.(error);
  }
}

export async function streamAssistantSpeech(text, { signal, onChunk = () => {}, onHeaders = () => {} } = {}) {
  const token = localStorage.getItem("campus_access_token");
  const response = await fetch(`${BASE_URL}/assistant/tts`, {
    method: "POST", headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ text }), signal,
  });
  if (!response.ok) throw new Error(`语音服务错误 (${response.status})`);
  const reader = response.body?.getReader();
  if (!reader) throw new Error("当前浏览器不支持流式语音");
  onHeaders(response.headers);
  while (true) { const { done, value } = await reader.read(); if (done) break; if (value?.byteLength) await onChunk(value); }
}

export async function extractNotice(text) { return dataOf(await client.post("/notices/extract-multi", { content: text })); }

export async function downloadAssignmentAttachment(assignmentId, attachmentId, filename = "作业附件") {
  const response = await client.get(`/assignments/${assignmentId}/attachments/${attachmentId}`, { responseType: "blob" });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || "作业附件";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export default client;
