import client from "./api";

const pageItems = (data) => data?.items || [];

export async function getStudentDashboard() {
  const { data } = await client.get("/dashboard/student");
  return data;
}

export async function getStudentCourses(params = {}) {
  const { data } = await client.get("/courses", { params: { page_size: 100, ...params } });
  return data;
}

export async function getStudentClasses(courseId) {
  const { data } = await client.get("/classes", { params: { page_size: 100, ...(courseId ? { course_id: courseId } : {}) } });
  return data;
}

export async function getCourseDetail(courseId) {
  const [courseResponse, classes, contentSummary, content] = await Promise.all([
    client.get(`/courses/${courseId}`),
    getStudentClasses(courseId),
    client.get(`/courses/${courseId}/content-summary`).catch(() => ({ data: null })),
    client.get(`/courses/${courseId}/content`, { params: { page_size: 500 } }).catch(() => ({ data: { items: [] } })),
  ]);
  const course = courseResponse.data;
  const classItems = classes.items || [];
  const grouped = await Promise.all(classItems.map(async (classItem) => {
    const [assignments, announcements] = await Promise.all([
      client.get(`/classes/${classItem.id}/assignments`, { params: { page_size: 100 } }),
      client.get(`/classes/${classItem.id}/announcements`, { params: { page_size: 100 } }),
    ]);
    return {
      ...classItem,
      assignments: pageItems(assignments.data),
      announcements: pageItems(announcements.data),
    };
  }));
  return { course, classes: grouped, contentSummary: contentSummary.data, remoteContent: pageItems(content.data) };
}

export async function syncCourseContent(courseId) {
  const { data } = await client.post(`/courses/${courseId}/sync`);
  return data;
}

export async function downloadCourseResource(courseId, itemId, filename = "课程资料") {
  const { data, headers } = await client.get(
    `/courses/${courseId}/resources/${itemId}/download`,
    { responseType: "blob" },
  );
  const url = URL.createObjectURL(data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || headers["content-disposition"] || "课程资料";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function getCourseResourceOpenUrl(courseId, itemId) {
  const { data } = await client.get(`/courses/${courseId}/resources/${itemId}/open`);
  return data;
}

export async function getStudentAssignments(params = {}) {
  const { data } = await client.get("/student/assignments", { params: { page_size: 100, ...params } });
  return data;
}

export async function getPersonalTasks(params = {}) {
  const { data } = await client.get("/tasks", { params: { page_size: 100, ...params } });
  return data;
}

export async function getStudentNotices(params = {}) {
  const { data } = await client.get("/notices", { params: { page_size: 200, ...params } });
  return data;
}

export async function getPersonalTask(id) {
  const { data } = await client.get(`/tasks/${id}`);
  return data;
}

export async function createPersonalTask(payload) {
  const { data } = await client.post("/tasks", payload);
  return data;
}

export async function updatePersonalTask(id, payload) {
  const { data } = await client.patch(`/tasks/${id}`, payload);
  return data;
}

export async function completePersonalTask(id, completed = true) {
  const { data } = await client.post(`/tasks/${id}/${completed ? "complete" : "restore"}`);
  return data;
}

export async function deletePersonalTask(id) {
  const { data } = await client.delete(`/tasks/${id}`);
  return data;
}

export async function getAssignment(id) {
  const { data } = await client.get(`/assignments/${id}`);
  return data;
}

export async function getMySubmission(assignmentId) {
  try {
    const { data } = await client.get(`/assignments/${assignmentId}/my-submission`);
    return data;
  } catch (error) {
    if (error.response?.status === 404) return null;
    throw error;
  }
}

export async function saveMySubmission(assignmentId, payload) {
  const { data } = await client.post(`/assignments/${assignmentId}/submissions`, payload);
  return data;
}

export async function submitMySubmission(id) {
  const { data } = await client.post(`/submissions/${id}/submit`);
  return data;
}

export async function getStudentActivities(params = {}) {
  const { data } = await client.get("/activities", { params: { page_size: 100, ...params } });
  return data;
}

export async function getStudentActivity(id) {
  const { data } = await client.get(`/activities/${id}`);
  return data;
}

export async function getActivityRegistration(id) {
  const { data } = await client.get(`/activities/${id}/registration`);
  return data;
}

export async function registerActivity(id) {
  const { data } = await client.post(`/activities/${id}/registration`);
  return data;
}

export async function cancelActivityRegistration(id) {
  const { data } = await client.delete(`/activities/${id}/registration`);
  return data;
}

export async function getAnnouncement(id) {
  const { data } = await client.get(`/announcements/${id}`);
  return data;
}

export async function markAnnouncementRead(id) {
  const { data } = await client.post(`/announcements/${id}/read`);
  return data;
}

export async function getStudentProfile() {
  const { data } = await client.get("/auth/me");
  return data.user || data;
}

export async function updateStudentProfile(payload) {
  const { data } = await client.patch("/admin/profile", payload);
  return data;
}

export async function getStudySessions(params = {}) {
  const { data } = await client.get("/study/sessions", { params: { page_size: 100, ...params } });
  return data;
}

export async function getActiveStudySession() {
  const { data } = await client.get("/study/sessions/active");
  return data;
}

export async function startStudySession(payload) {
  const { data } = await client.post("/study/sessions", payload);
  return data;
}

export async function pauseStudySession(id, reason) {
  const { data } = await client.post(`/study/sessions/${id}/pause`, null, { params: reason ? { reason } : {} });
  return data;
}

export async function resumeStudySession(id) {
  const { data } = await client.post(`/study/sessions/${id}/resume`);
  return data;
}

export async function finishStudySession(id, payload = {}) {
  const { data } = await client.post(`/study/sessions/${id}/finish`, payload);
  return data;
}

export async function breakdownStudyTask(payload) {
  const { data } = await client.post("/study/task-breakdown", payload);
  return data;
}

export async function getStudentExams(params = {}) {
  const { data } = await client.get("/student/exams", { params });
  return data;
}

export async function saveStudentExam(payload, id) {
  const { data } = id ? await client.patch(`/student/exams/${id}`, payload) : await client.post("/student/exams", payload);
  return data;
}

export async function deleteStudentExam(id) {
  const { data } = await client.delete(`/student/exams/${id}`);
  return data;
}

export async function getClassroomOptions(params = {}) {
  const { data } = await client.get("/student/classrooms", { params });
  return data;
}

export async function getServiceRequests(params = {}) {
  const { data } = await client.get("/student/service-requests", { params });
  return data;
}

export async function getServiceRequest(id) {
  const { data } = await client.get(`/student/service-requests/${id}`);
  return data;
}

export async function createServiceRequest(payload) {
  const { data } = await client.post("/student/service-requests", payload);
  return data;
}

export async function getLostFound(params = {}) {
  const { data } = await client.get("/student/lost-found", { params });
  return data;
}

export async function getLostFoundItem(id) {
  const { data } = await client.get(`/student/lost-found/${id}`);
  return data;
}

export async function createLostFound(payload) {
  const { data } = await client.post("/student/lost-found", payload);
  return data;
}

export async function deleteLostFound(id) {
  const { data } = await client.delete(`/student/lost-found/${id}`);
  return data;
}

export async function getUniversities(params = {}) {
  const { data } = await client.get("/universities", { params });
  return data;
}
export async function selectUniversity(universityId) {
  const { data } = await client.put("/profile/university", { university_id: universityId });
  return data;
}
export async function getCommunityPosts(params = {}) {
  const { data } = await client.get("/community/posts", { params });
  return data;
}
export async function createCommunityPost(payload) {
  const { data } = await client.post("/community/posts", payload);
  return data;
}
export async function likeCommunityPost(id) {
  const { data } = await client.post(`/community/posts/${id}/like`);
  return data;
}
export async function favoriteCommunityPost(id) {
  const { data } = await client.post(`/community/posts/${id}/favorite`);
  return data;
}
export async function getAcademicStatus() {
  const { data } = await client.get("/academic/status");
  return data;
}
export async function getAcademicProviders() {
  const { data } = await client.get("/academic/providers");
  return data;
}

// ===== CampusMate EduConnector =====
export async function eduDetect(universityId) {
  const { data } = await client.get("/edu/detect", { params: { university_id: universityId } });
  return data;
}
export async function getEduConfig(universityId) {
  const { data } = await client.get(`/edu/config/${universityId}`);
  return data;
}
export async function getEduBinding() {
  const { data } = await client.get("/edu/binding");
  return data;
}
export async function eduBind(username, password, systemType = "undergrad") {
  const { data } = await client.post("/edu/bind", { username, password, system_type: systemType });
  return data;
}
export async function eduUnbind() {
  const { data } = await client.delete("/edu/binding");
  return data;
}
export async function eduSync(syncType, params = {}) {
  const { data } = await client.post(`/edu/sync/${syncType}`, null, { params });
  return data;
}
export async function getEduSyncRecords(limit = 20) {
  const { data } = await client.get("/edu/sync/records", { params: { limit } });
  return data;
}
