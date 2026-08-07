import client from "./api";

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
