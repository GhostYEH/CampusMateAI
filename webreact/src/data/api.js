import { itemsOf, studySessionPayload } from "./contracts.js";
import { BASE_URL, client } from "./http/client.js";

export { BASE_URL, client, createClient, refreshAccessToken, saveTokenPair, applyTokenPair } from "./http/client.js";
export { probeBackend, login, getDeviceId, qrCreate, qrStatus, qrExchange, trustedDeviceAutoLogin, revokeTrustedDevice } from "./http/authEndpoints.js";

const dataOf = (response) => response.data;
const revisionHeaders = (revision) => ({ "If-Match": String(revision) });

export async function getDashboard() { return dataOf(await client.get("/dashboard/student")); }
/**
 * 全站统一的"今日待办"事实源。
 * 首页、学习陪伴、任务总览、全局角标都读这一个接口，前端不再各自组合过滤。
 */
export async function getTodayAgenda() { return dataOf(await client.get("/agenda/today")); }
export async function getCourses(params = {}) { return dataOf(await client.get("/courses", { params: { page_size: 100, ...params } })); }
export async function getClasses(courseId) { return dataOf(await client.get("/classes", { params: { page_size: 100, ...(courseId ? { course_id: courseId } : {}) } })); }

export async function getCourse(courseId) { return dataOf(await client.get(`/courses/${courseId}`)); }

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

export async function syncCourse(courseId, depth = "fast", sections = null) {
  return dataOf(await client.post(`/courses/${courseId}/sync`, null, {
    params: sections?.length ? { depth, sections: sections.join(",") } : { depth },
  }));
}
export async function getCourseKnowledgeGraph(courseId) {
  return dataOf(await client.get(`/courses/${courseId}/knowledge-graph`));
}
export async function openCourseResource(courseId, itemId) { return dataOf(await client.get(`/courses/${courseId}/resources/${itemId}/open`)); }
function triggerBlobDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
export async function downloadCourseResource(courseId, itemId, filename = "课程资料") {
  const response = await client.get(`/courses/${courseId}/resources/${itemId}/download`, { responseType: "blob" });
  triggerBlobDownload(response.data, filename || response.headers["content-disposition"] || "课程资料");
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
export async function getDailyStudyGoal() { return dataOf(await client.get("/study/goals/daily")); }
export async function updateDailyStudyGoal(targetMinutes) { return dataOf(await client.put("/study/goals/daily", { target_minutes: targetMinutes })); }
export async function startStudySession(payload) { return dataOf(await client.post("/study/sessions", studySessionPayload(payload))); }
export async function pauseStudySession(id, reason) { return dataOf(await client.post(`/study/sessions/${id}/pause`, null, { params: reason ? { reason } : {} })); }
export async function resumeStudySession(id) { return dataOf(await client.post(`/study/sessions/${id}/resume`)); }
export async function finishStudySession(id, payload = {}) { return dataOf(await client.post(`/study/sessions/${id}/finish`, payload)); }
export async function breakdownStudyTask(payload) {
  // 任务拆解会调用 LLM,后端默认超时 30s。前端独立设置 45s,
  // 既大于后端模型超时以容纳网络往返,又不影响其它普通 API 的 8s 默认超时。
  return dataOf(await client.post("/study/task-breakdown", payload, { timeout: 45000 }));
}
async function studyCheckinsSupported() {
  try {
    const response = await client.get("/health");
    return response.data?.study_checkins_supported === true;
  } catch {
    return false;
  }
}
export async function getStudyCheckins() {
  if (!(await studyCheckinsSupported())) return { items: [], total: 0, streak: 0, longest_streak: 0, week_count: 0, today_checked: false, unsupported: true };
  return dataOf(await client.get("/study/checkins"));
}
export async function createStudyCheckin(payload = {}) {
  if (!(await studyCheckinsSupported())) {
    const error = new Error("签到服务尚未加载，请重启当前后端服务后重试。");
    error.code = "STUDY_CHECKINS_UNAVAILABLE";
    throw error;
  }
  return dataOf(await client.post("/study/checkins", payload));
}
export async function getKnowledgeDocuments() { return dataOf(await client.get("/knowledge/documents")); }

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

// ===== 课程智能辅导空间（magic class 学生侧互动课堂）=====
// 只能经 CampusMate 后端触达 magic class，不直连、不在前端保存任何 magic class 访问资料。

/**
 * 查询互动课堂能力状态。未配置服务 / 请求失败时不抛出 —— 返回 enabled:false，
 * 让课程详情其余标签不受影响。unavailable 标记请求层面的不可用。
 */
export async function getInteractiveClassroomStatus(courseId) {
  try {
    return dataOf(await client.get(`/courses/${courseId}/interactive-classroom/status`));
  } catch (error) {
    return { enabled: false, unavailable: true, reason: error?.message || "服务暂不可用" };
  }
}

/** 生成前的只读计划：课程、可选资料、推荐形态与理由。不创建任何 magic class 任务。 */
export async function getInteractiveClassroomPlan(courseId, mode = "adaptive") {
  return dataOf(
    await client.get(
      `/courses/${courseId}/interactive-classroom/plan?mode=${encodeURIComponent(mode)}`,
    ),
  );
}

/** 把学生简报里已填写的字段挑出来（空值不发送，避免污染 requirement）。 */
function interactiveBriefPayload(payload = {}) {
  const out = {};
  if (payload.learning_objective) out.learning_objective = payload.learning_objective;
  if (payload.current_difficulty) out.current_difficulty = payload.current_difficulty;
  if (payload.desired_duration_minutes) out.desired_duration_minutes = payload.desired_duration_minutes;
  if (payload.difficulty_level) out.difficulty_level = payload.difficulty_level;
  if (payload.wants_more_practice) out.wants_more_practice = true;
  if (Array.isArray(payload.selected_material_ids) && payload.selected_material_ids.length) {
    out.selected_material_ids = payload.selected_material_ids;
  }
  return out;
}

/** 提交一次课堂生成，返回 202 与初始 session（含 session_id / poll_interval_ms）。 */
export async function generateInteractiveClassroom(courseId, payload) {
  return dataOf(await client.post(`/courses/${courseId}/interactive-classroom/generate`, { mode: payload.mode, ...interactiveBriefPayload(payload) }));
}

/** 回读这节课**真实**包含的内容（scene 类型统计 / widget 分布 / 白板 / TTS / 多智能体）。 */
export async function getInteractiveClassroomComposition(courseId, sessionId) {
  return dataOf(await client.get(`/courses/${courseId}/interactive-classroom/${sessionId}/composition`));
}

/** 轮询生成进度（服务端会现场轮询一次 magic class 后返回）。 */
export async function getInteractiveClassroomJob(courseId, sessionId) {
  return dataOf(await client.get(`/courses/${courseId}/interactive-classroom/jobs/${sessionId}`));
}

/** 列出该课程已生成的课堂。 */
export async function listInteractiveClassrooms(courseId) {
  return dataOf(await client.get(`/courses/${courseId}/interactive-classroom`));
}

/**
 * 受管 magic class 服务的公开状态。
 * `state` 是唯一判据：disabled / unavailable / degraded / ready。
 * 只有 ready 时 `capabilities` 才非空。
 */
export async function getMagicClassFusionStatus() {
  return dataOf(await client.get("/magicclass/fusion/status"));
}

/**
 * 跨课程"最近内容"聚合（服务端已按权限过滤并按 updated_at 倒序）。
 * 取代浏览器对前 N 门课程分别发历史请求。
 */
export async function getMagicClassRecent(limit = 20) {
  return dataOf(await client.get("/magicclass/fusion/recent", { params: { limit } }));
}

export async function getMagicClassProviderStatus() {
  return dataOf(await client.get("/magicclass/fusion/providers"));
}

/**
 * 生成前的只读课程上下文：这门课已同步的知识点、章节与可用资料。
 *
 * 只读且只读本地库——它不经过受管 magic class 服务，所以受管服务不可用时它依然
 * 可用。界面据此如实说明"这次能拿什么去生成"，而不是编一份听起来合理的主题。
 */
export async function getMagicClassCourseContext(courseId) {
  return dataOf(await client.get(`/courses/${courseId}/magicclass-context`));
}

// ===== 学习工作台（workspace / stage） =====
//
// 两个头是**协议的一部分**，不是可选优化：
// - 创建必须带 Idempotency-Key，用同一个键重试会拿回同一个工作台而不是再建一个；
// - 条件写入必须带 If-Match（当前 revision），否则并发修改会被静默覆盖。

/** 创建时使用的幂等键。同一个用户动作重试必须复用同一个键。 */
export function newIdempotencyKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `idem-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export async function listMagicClassWorkspaces(courseId, { limit = 20, cursor = null } = {}) {
  return dataOf(
    await client.get(`/courses/${courseId}/workspaces`, {
      params: { limit, ...(cursor ? { cursor } : {}) },
    }),
  );
}

export async function createMagicClassWorkspace(courseId, { name, description = "", folderId, idempotencyKey }) {
  return dataOf(
    await client.post(
      `/courses/${courseId}/workspaces`,
      { name, description, ...(folderId === undefined || folderId === null ? {} : { folder_id: folderId }) },
      { headers: { "Idempotency-Key": idempotencyKey } },
    ),
  );
}

export async function getMagicClassWorkspace(courseId, workspaceId) {
  return dataOf(await client.get(`/courses/${courseId}/workspaces/${workspaceId}`));
}

/**
 * 条件更新工作台。
 *
 * `folderId` 的三种取值含义不同，必须原样传下去：`undefined` = 不动归档位置，
 * `null` = 取消归档，字符串 = 归档到该文件夹。把它折叠成一种会让"取消归档"
 * 变成"什么都不做"。
 */
export async function updateMagicClassWorkspace(courseId, workspaceId, { revision, name, description, folderId }) {
  const payload = {};
  if (name !== undefined) payload.name = name;
  if (description !== undefined) payload.description = description;
  if (folderId !== undefined) payload.folder_id = folderId;
  return dataOf(
    await client.patch(`/courses/${courseId}/workspaces/${workspaceId}`, payload, {
      headers: revisionHeaders(revision),
    }),
  );
}

export async function deleteMagicClassWorkspace(courseId, workspaceId, { revision }) {
  return dataOf(
    await client.delete(`/courses/${courseId}/workspaces/${workspaceId}`, {
      headers: revisionHeaders(revision),
    }),
  );
}

export async function listMagicClassStages(courseId, workspaceId, { limit = 20, cursor = null } = {}) {
  return dataOf(
    await client.get(`/courses/${courseId}/workspaces/${workspaceId}/stages`, {
      params: { limit, ...(cursor ? { cursor } : {}) },
    }),
  );
}

export async function getMagicClassStage(courseId, workspaceId, stageId) {
  return dataOf(await client.get(`/courses/${courseId}/workspaces/${workspaceId}/stages/${stageId}`));
}

export async function createMagicClassStage(courseId, workspaceId, { title, document = null, idempotencyKey }) {
  return dataOf(
    await client.post(
      `/courses/${courseId}/workspaces/${workspaceId}/stages`,
      { title, ...(document ? { document } : {}) },
      { headers: { "Idempotency-Key": idempotencyKey } },
    ),
  );
}

export async function replaceMagicClassStage(courseId, workspaceId, stageId, { revision, document, title }) {
  return dataOf(
    await client.put(
      `/courses/${courseId}/workspaces/${workspaceId}/stages/${stageId}`,
      { document, ...(title === undefined ? {} : { title }) },
      { headers: revisionHeaders(revision) },
    ),
  );
}

export async function deleteMagicClassStage(courseId, workspaceId, stageId, { revision }) {
  return dataOf(
    await client.delete(`/courses/${courseId}/workspaces/${workspaceId}/stages/${stageId}`, {
      headers: revisionHeaders(revision),
    }),
  );
}

export async function generateMagicClassStage(courseId, workspaceId, { mode, prompt, roleMode = "preset", selectedRoleIds = [], idempotencyKey }) {
  return dataOf(await client.post(
    `/courses/${courseId}/workspaces/${workspaceId}/generate`,
    { mode, prompt, role_mode: roleMode, selected_role_ids: selectedRoleIds },
    { headers: { "Idempotency-Key": idempotencyKey } },
  ));
}

/** 首页一次性生成：网关原子解析/创建课程工作台并排队首个 stage。 */
export async function generateMagicClassHome(courseId, { mode = "slide", prompt, idempotencyKey }) {
  return dataOf(await client.post(
    `/courses/${courseId}/home-generate`,
    { mode, prompt },
    { headers: { "Idempotency-Key": idempotencyKey } },
  ));
}

export async function getMagicClassJob(courseId, jobId) {
  return dataOf(await client.get(`/courses/${courseId}/jobs/${jobId}`));
}

export async function cancelMagicClassJob(courseId, jobId) {
  return dataOf(await client.post(`/courses/${courseId}/jobs/${jobId}/cancel`));
}

export async function retryMagicClassJob(courseId, jobId) {
  return dataOf(await client.post(`/courses/${courseId}/jobs/${jobId}/retry`));
}

export async function synthesizeMagicClassTts(courseId, { text, instruction, voice, idempotencyKey }) {
  return dataOf(await client.post(
    `/courses/${courseId}/tts`,
    { text, ...(instruction ? { instruction } : {}), ...(voice ? { voice } : {}) },
    { headers: { "Idempotency-Key": idempotencyKey } },
  ));
}

export async function runMagicClassDiscussion(courseId, { prompt, idempotencyKey }) {
  return dataOf(await client.post(
    `/courses/${courseId}/discussion`,
    { prompt },
    { headers: { "Idempotency-Key": idempotencyKey } },
  ));
}

/**
 * 读取某个场景的讲解音频状态。
 *
 * 请求里只带 scene id，不带任何文本：讲稿由服务端从这一页的正文派生，所以
 * "这一页的音频"与"这一页的内容"不可能对不上。返回里 `job` 为 null 表示这一页
 * 还没有音频（或讲稿为空，看 `has_script`）。
 */
export async function getMagicClassSceneNarration(courseId, workspaceId, stageId, sceneId) {
  return dataOf(await client.get(
    `/courses/${courseId}/workspaces/${workspaceId}/stages/${stageId}/scenes/${sceneId}/narration`,
  ));
}

/**
 * 为**一个**场景排队生成讲解音频。
 *
 * 显式传 sceneId 作为幂等键的一部分：同一页重复点击应复用同一个任务，而不是
 * 再付一次 TTS。真正的去重由服务端做（已完成/在飞/幂等键三层），这里只是让
 * 默认键对同一页稳定。
 */
export async function synthesizeMagicClassSceneNarration(courseId, workspaceId, stageId, sceneId, { idempotencyKey } = {}) {
  const key = idempotencyKey || `narration:${courseId}:${stageId}:${sceneId}`;
  return dataOf(await client.post(
    `/courses/${courseId}/workspaces/${workspaceId}/stages/${stageId}/scenes/${sceneId}/narration`,
    { scene_id: sceneId, stage_id: stageId },
    { headers: { "Idempotency-Key": key } },
  ));
}

export async function getMagicClassArtifact(courseId, artifactId) {
  const response = await client.get(`/courses/${courseId}/artifacts/${artifactId}`, { responseType: "blob" });
  return {
    blob: response.data,
    disposition: response.headers?.["content-disposition"] || "",
    mediaType: response.headers?.["content-type"] || "",
  };
}

export async function enqueueMagicClassStageVideo(courseId, workspaceId, stageId, { idempotencyKey }) {
  return dataOf(await client.post(
    `/courses/${courseId}/workspaces/${workspaceId}/stages/${stageId}/export/video`,
    {},
    { headers: { "Idempotency-Key": idempotencyKey } },
  ));
}

export async function addMagicClassWhiteboard(courseId, workspaceId, stageId, { board, revision, idempotencyKey }) {
  return dataOf(await client.post(
    `/courses/${courseId}/workspaces/${workspaceId}/stages/${stageId}/whiteboard`,
    { board },
    { headers: { "Idempotency-Key": idempotencyKey, ...revisionHeaders(revision) } },
  ));
}

// ===== 文件夹与站内搜索 =====
//
// 两者都只经 CampusMate 后端。搜索的关键词长度与空值在网关和受管服务各校验
// 一次；前端这里只负责"空关键词不发请求"，避免把"没输入"变成"返回全部"。

export async function listMagicClassFolders(courseId, { limit = 20, cursor = null } = {}) {
  return dataOf(
    await client.get(`/courses/${courseId}/folders`, {
      params: { limit, ...(cursor ? { cursor } : {}) },
    }),
  );
}

export async function createMagicClassFolder(courseId, { name, parentId = null, idempotencyKey }) {
  return dataOf(
    await client.post(
      `/courses/${courseId}/folders`,
      { name, ...(parentId ? { parent_id: parentId } : {}) },
      { headers: { "Idempotency-Key": idempotencyKey } },
    ),
  );
}

export async function getMagicClassFolder(courseId, folderId) {
  return dataOf(await client.get(`/courses/${courseId}/folders/${folderId}`));
}

/** `parentId` 为 `null` 表示移动到根层；`undefined` 表示不改层级。 */
export async function updateMagicClassFolder(courseId, folderId, { revision, name, parentId }) {
  const payload = {};
  if (name !== undefined) payload.name = name;
  if (parentId !== undefined) payload.parent_id = parentId;
  return dataOf(
    await client.patch(`/courses/${courseId}/folders/${folderId}`, payload, {
      headers: revisionHeaders(revision),
    }),
  );
}

export async function deleteMagicClassFolder(courseId, folderId, { revision }) {
  return dataOf(
    await client.delete(`/courses/${courseId}/folders/${folderId}`, {
      headers: revisionHeaders(revision),
    }),
  );
}

export async function searchMagicClassContent(courseId, { query, limit = 20, cursor = null }) {
  return dataOf(
    await client.get(`/courses/${courseId}/search`, {
      params: { q: query, limit, ...(cursor ? { cursor } : {}) },
    }),
  );
}

// ===== 课程资料 =====
//
// 上传是**多部分表单**：文件字节只走这一条路，且只在 CampusMate 网关与浏览器
// 之间。网关解析出正文后才调用受管服务，所以内部调用里从来没有文件本身。
// 创建必须带 Idempotency-Key（重试不能变成第二份资料），删除必须带 If-Match。

export async function listMagicClassMaterials(courseId, { limit = 20, cursor = null } = {}) {
  return dataOf(
    await client.get(`/courses/${courseId}/materials`, {
      params: { limit, ...(cursor ? { cursor } : {}) },
    }),
  );
}

export async function uploadMagicClassMaterial(courseId, { file, idempotencyKey }) {
  const form = new FormData();
  form.append("file", file);
  return dataOf(
    await client.post(`/courses/${courseId}/materials`, form, {
      headers: { "Content-Type": "multipart/form-data", "Idempotency-Key": idempotencyKey },
    }),
  );
}

/** 唯一会返回正文的资料接口。 */
export async function getMagicClassMaterial(courseId, materialId) {
  return dataOf(await client.get(`/courses/${courseId}/materials/${materialId}`));
}

export async function deleteMagicClassMaterial(courseId, materialId, { revision }) {
  return dataOf(
    await client.delete(`/courses/${courseId}/materials/${materialId}`, {
      headers: revisionHeaders(revision),
    }),
  );
}

/** 批量解析引用：返回服务端**授权过**的引用与没能解析到的 id。 */
export async function resolveMagicClassMaterials(courseId, { materialIds }) {
  return dataOf(
    await client.post(`/courses/${courseId}/materials/resolve`, { material_ids: materialIds }),
  );
}

// ===== `.maic.zip` 导出 / 导入 =====
//
// 导出返回的是**字节**，不是 JSON：档案是学生要保存的文件。响应类型必须是 blob，
// 否则 axios 会把 zip 当文本处理。下载名由服务端放在 `Content-Disposition` 里
// （中文走 RFC 5987 的 filename*），前端只解析、不自己拼。
// 导入用多部分表单：学生选的是文件，网关负责把它编码成内部调用需要的形状。

function archiveResult(response) {
  return {
    blob: response.data,
    disposition: response.headers?.["content-disposition"] || "",
    sha256: response.headers?.["x-archive-sha256"] || "",
  };
}

export async function exportMagicClassStage(courseId, workspaceId, stageId) {
  const response = await client.get(
    `/courses/${courseId}/workspaces/${workspaceId}/stages/${stageId}/export`,
    { responseType: "blob" },
  );
  return archiveResult(response);
}

export async function exportMagicClassStageFormat(courseId, workspaceId, stageId, format) {
  const response = await client.get(
    `/courses/${courseId}/workspaces/${workspaceId}/stages/${stageId}/export/${format}`,
    { responseType: "blob" },
  );
  return archiveResult(response);
}

export async function importMagicClassStage(courseId, workspaceId, { file, idempotencyKey }) {
  const form = new FormData();
  form.append("file", file);
  return dataOf(
    await client.post(`/courses/${courseId}/workspaces/${workspaceId}/import`, form, {
      headers: { "Content-Type": "multipart/form-data", "Idempotency-Key": idempotencyKey },
    }),
  );
}

export async function importMagicClassPptx(courseId, workspaceId, { file, idempotencyKey }) {
  const form = new FormData();
  form.append("file", file);
  return dataOf(
    await client.post(`/courses/${courseId}/workspaces/${workspaceId}/import/pptx`, form, {
      headers: { "Content-Type": "multipart/form-data", "Idempotency-Key": idempotencyKey },
    }),
  );
}

// ===== 编辑器（Stage 命令） =====
//
// 提交的是**命令列表**，不是整份文档：整份回传会让没看到并发修改的作者静默
// 回退别人的改动。两个头同样属于协议：Idempotency-Key 防止重试重复建场景，
// If-Match 携带这组命令所基于的 revision。

export async function getMagicClassStageOutline(courseId, workspaceId, stageId) {
  return dataOf(
    await client.get(`/courses/${courseId}/workspaces/${workspaceId}/stages/${stageId}/outline`),
  );
}

/** 播放计划（渲染决定 + 恢复位置）。`sceneId` 是刷新后要回到的场景。 */
export async function getMagicClassStagePlayback(courseId, workspaceId, stageId, { sceneId = null } = {}) {
  return dataOf(
    await client.get(`/courses/${courseId}/workspaces/${workspaceId}/stages/${stageId}/playback`, {
      params: sceneId ? { scene_id: sceneId } : {},
    }),
  );
}

export async function getMagicClassStageScene(courseId, workspaceId, stageId, sceneId) {
  return dataOf(
    await client.get(
      `/courses/${courseId}/workspaces/${workspaceId}/stages/${stageId}/scenes/${sceneId}`,
    ),
  );
}

export async function getMagicClassQuizAttempt(courseId, workspaceId, stageId, sceneId) {
  return dataOf(await client.get(`/courses/${courseId}/workspaces/${workspaceId}/stages/${stageId}/scenes/${sceneId}/quiz-attempt`));
}

export async function saveMagicClassQuizAttempt(courseId, workspaceId, stageId, sceneId, payload) {
  return dataOf(await client.post(`/courses/${courseId}/workspaces/${workspaceId}/stages/${stageId}/scenes/${sceneId}/quiz-attempt`, payload));
}

export async function applyMagicClassStageCommands(courseId, workspaceId, stageId, { commands, revision, idempotencyKey }) {
  return dataOf(
    await client.post(
      `/courses/${courseId}/workspaces/${workspaceId}/stages/${stageId}/commands`,
      { commands },
      { headers: { "Idempotency-Key": idempotencyKey, ...revisionHeaders(revision) } },
    ),
  );
}

/** 失败时重试生成。 */
export async function retryInteractiveClassroom(courseId, sessionId, payload) {
  return dataOf(await client.post(`/courses/${courseId}/interactive-classroom/${sessionId}/retry`, { mode: payload.mode, ...interactiveBriefPayload(payload) }));
}

/** 创建一个受管 Agent 任务（互动课堂生成走这里，前端不直接调用 magic class）。 */
export async function createAgentJob(payload) {
  return dataOf(await client.post("/agent-jobs", payload));
}

/** 查询 Agent 任务（含 input_ref 上回填的 session_id / deep_link）。 */
export async function getAgentJob(jobId) {
  return dataOf(await client.get(`/agent-jobs/${jobId}`));
}

/** 审批决策：APPROVED / REJECTED。 */
export async function decideAgentApproval(approvalId, decision, reason) {
  return dataOf(
    await client.post(`/agent-approvals/${approvalId}/decision`, {
      decision,
      ...(reason ? { reason } : {}),
    }),
  );
}

export async function chatStream(message, { onSources, onChunk, onDone, onError, signal, webSearch = false, attachment = null, conversationId = null, recentTasks = [], courseId = null, workspaceId = null } = {}) {
  try {
    const token = localStorage.getItem("campus_access_token");
    const response = await fetch(`${BASE_URL}/counselor/chat`, {
      method: "POST", headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({
        message, stream: true, web_search: webSearch, attachment, recent_tasks: recentTasks,
        ...(conversationId ? { conversation_id: conversationId } : {}),
        ...(courseId ? { course_id: courseId } : {}),
        ...(workspaceId ? { workspace_id: workspaceId } : {}),
      }), signal,
    });
    if (!response.ok) throw new Error(`服务器错误 (${response.status})`);
    const reader = response.body?.getReader();
    if (!reader) throw new Error("浏览器不支持流式读取");
    const decoder = new TextDecoder();
    let buffer = "";
    // 同一个流里只认第一个 done：重连/代理重放导致的重复 done 不得二次触发副作用。
    let doneSeen = false;
    const consume = (block) => {
      let type = "";
      const dataLines = [];
      block.split("\n").forEach((rawLine) => {
        const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
        if (!line || line.startsWith(":")) return; // 空行 / 注释 / 心跳
        if (line.startsWith("event:")) {
          type = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          // SSE 规范：冒号后可选一个空格；多行 data 用 \n 连接
          dataLines.push(line.slice(5).replace(/^ /, ""));
        }
      });
      if (!dataLines.length) return;
      const dataText = dataLines.join("\n");
      try {
        const data = JSON.parse(dataText);
        if (type === "sources") onSources?.(data.sources || []);
        else if (type === "chunk") onChunk?.(data.text || "", data.mode || "llm");
        else if (type === "done") {
          if (doneSeen) return;
          doneSeen = true;
          onDone?.(data);
        } else if (type === "error") onError?.(new Error(data.message || "未知错误"));
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
  triggerBlobDownload(response.data, filename || "作业附件");
}

export default client;
