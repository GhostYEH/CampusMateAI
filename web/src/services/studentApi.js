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
  const [courseResponse, classes] = await Promise.all([
    client.get(`/courses/${courseId}`),
    getStudentClasses(courseId),
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
  return { course, classes: grouped };
}

export async function getStudentAssignments(params = {}) {
  const { data } = await client.get("/student/assignments", { params: { page_size: 100, ...params } });
  return data;
}

export async function getPersonalTasks(params = {}) {
  const { data } = await client.get("/tasks", { params: { page_size: 100, ...params } });
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
