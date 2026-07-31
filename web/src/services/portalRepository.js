import client from "./api";

export async function getTeacherOverview() {
  const { data } = await client.get("/dashboard/teacher");
  return data;
}

export async function getTeacherCourses() {
  const [{ data: coursePage }, { data: classPage }] = await Promise.all([
    client.get("/courses", { params: { page_size: 100 } }),
    client.get("/classes", { params: { page_size: 100 } }),
  ]);
  return { courses: coursePage.items || [], classes: classPage.items || [] };
}

export async function getTeacherAssignments() {
  const { classes } = await getTeacherCourses();
  const pages = await Promise.all(
    classes.map((cls) => client.get(`/classes/${cls.id}/assignments`, { params: { page_size: 100 } })),
  );
  return pages.flatMap((response, index) =>
    (response.data.items || []).map((item) => ({ ...item, class_name: classes[index].name })),
  );
}

export async function createTeacherAssignment(payload) {
  const { class_group_id, ...body } = payload;
  const { data } = await client.post(`/classes/${class_group_id}/assignments`, body);
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

export async function updateAssignmentStatus(assignmentId, status) {
  const action = status === "published" ? "publish" : "close";
  const { data } = await client.post(`/assignments/${assignmentId}/${action}`);
  return data;
}

export async function getAssignmentInsight(assignment) {
  const [{ data: stats }, { data: students }] = await Promise.all([
    client.get(`/assignments/${assignment.id}/stats`),
    client.get(`/assignments/${assignment.id}/student-status`, { params: { page_size: 100 } }),
  ]);
  return { stats, students: students.items || [] };
}

export async function getAdminUsers(filters = {}) {
  const { data } = await client.get("/auth/admin/users", { params: { ...filters, page_size: 100 } });
  return data;
}

export async function createAdminUser(payload) {
  const { data } = await client.post("/auth/admin/users", payload);
  return data;
}

export async function updateAdminUser(userId, payload) {
  const { data } = await client.patch(`/auth/admin/users/${userId}`, payload);
  return data;
}

export async function getActivities(filters = {}) {
  const { data } = await client.get("/activities", { params: { ...filters, page_size: 100 } });
  return data;
}

export async function createActivity(payload) {
  const { data } = await client.post("/admin/activities", payload);
  return data;
}

export async function updateActivityStatus(activityId, status) {
  const action = status === "published" ? "publish" : "close";
  const { data } = await client.post(`/admin/activities/${activityId}/${action}`);
  return data;
}

export async function getAdminOverview() {
  const [users, activities, courses] = await Promise.all([
    getAdminUsers(),
    getActivities(),
    client.get("/courses", { params: { page_size: 100 } }),
  ]);
  return {
    user_count: users.total,
    student_count: users.items.filter((item) => item.role === "student").length,
    teacher_count: users.items.filter((item) => item.role === "teacher").length,
    inactive_count: users.items.filter((item) => !item.is_active).length,
    activity_count: activities.total,
    published_activity_count: activities.items.filter((item) => item.status === "published").length,
    course_count: courses.data.total,
    recent_users: users.items.slice(0, 5),
    recent_activities: activities.items.slice(0, 4),
  };
}
