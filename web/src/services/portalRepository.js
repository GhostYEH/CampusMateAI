import client from "./api";
import { loadMockPortal, saveMockPortal } from "../data/mockPortal";

const delay = (ms = 260) => new Promise((resolve) => setTimeout(resolve, ms));
const nowId = (prefix) => `${prefix}_${Date.now().toString(36)}`;
const mock = () => loadMockPortal();

function className(data, classId) {
  return data.classes.find((item) => item.id === classId)?.name || "未命名班级";
}

function courseForClass(data, classId) {
  const cls = data.classes.find((item) => item.id === classId);
  return data.courses.find((item) => item.id === cls?.course_id);
}

export async function getTeacherOverview(useMock) {
  if (!useMock) {
    const { data } = await client.get("/dashboard/teacher");
    return data;
  }
  await delay();
  const data = mock();
  return {
    course_count: data.courses.length,
    class_count: data.classes.length,
    student_count: data.classes.reduce((sum, item) => sum + (item.capacity || 0), 0),
    active_assignment_count: data.assignments.filter((item) => item.status === "published").length,
    pending_submission_count: data.assignments
      .filter((item) => item.status === "published")
      .reduce((sum, item) => sum + Math.max(0, (item.student_count || 0) - (item.submitted_count || 0)), 0),
    overdue_student_count: 7,
    recent_assignments: data.assignments.slice(0, 5).map((item) => ({
      ...item,
      assignment_id: item.id,
      class_name: className(data, item.class_group_id),
      course_name: courseForClass(data, item.class_group_id)?.name,
    })),
  };
}

export async function getTeacherCourses(useMock) {
  if (!useMock) {
    const [{ data: coursePage }, { data: classPage }] = await Promise.all([
      client.get("/courses", { params: { page_size: 100 } }),
      client.get("/classes", { params: { page_size: 100 } }),
    ]);
    return { courses: coursePage.items || [], classes: classPage.items || [] };
  }
  await delay();
  const data = mock();
  return { courses: data.courses, classes: data.classes };
}

export async function getTeacherAssignments(useMock) {
  if (!useMock) {
    const { classes } = await getTeacherCourses(false);
    const pages = await Promise.all(
      classes.map((cls) => client.get(`/classes/${cls.id}/assignments`, { params: { page_size: 100 } })),
    );
    return pages.flatMap((response, index) =>
      (response.data.items || []).map((item) => ({ ...item, class_name: classes[index].name })),
    );
  }
  await delay();
  const data = mock();
  return data.assignments.map((item) => ({
    ...item,
    class_name: className(data, item.class_group_id),
    course_name: courseForClass(data, item.class_group_id)?.name,
  }));
}

export async function createTeacherAssignment(useMock, payload) {
  if (!useMock) {
    const { class_group_id, ...body } = payload;
    const { data } = await client.post(`/classes/${class_group_id}/assignments`, body);
    return data;
  }
  await delay(420);
  const data = mock();
  const cls = data.classes.find((item) => item.id === payload.class_group_id);
  const item = {
    id: nowId("asg"),
    ...payload,
    submitted_count: 0,
    student_count: cls?.capacity || 0,
    created_at: new Date().toISOString(),
    published_at: payload.status === "published" ? new Date().toISOString() : null,
  };
  data.assignments.unshift(item);
  saveMockPortal(data);
  return item;
}

export async function updateAssignmentStatus(useMock, assignmentId, status) {
  if (!useMock) {
    const action = status === "published" ? "publish" : "close";
    const { data } = await client.post(`/assignments/${assignmentId}/${action}`);
    return data;
  }
  await delay();
  const data = mock();
  const item = data.assignments.find((entry) => entry.id === assignmentId);
  if (!item) throw new Error("任务不存在");
  item.status = status;
  if (status === "published") item.published_at = new Date().toISOString();
  saveMockPortal(data);
  return item;
}

export async function getAssignmentInsight(useMock, assignment) {
  if (!useMock) {
    const [{ data: stats }, { data: students }] = await Promise.all([
      client.get(`/assignments/${assignment.id}/stats`),
      client.get(`/assignments/${assignment.id}/student-status`, { params: { page_size: 100 } }),
    ]);
    return { stats, students: students.items || [] };
  }
  await delay();
  const total = assignment.student_count || 42;
  const submitted = assignment.submitted_count || 0;
  const names = ["林知夏", "周予辰", "陈一诺", "沈佳禾", "许嘉言", "顾清越"];
  return {
    stats: {
      total_students: total,
      submitted_count: submitted,
      unsubmitted_count: Math.max(0, total - submitted),
      late_count: Math.min(3, submitted),
      graded_count: Math.max(0, submitted - 8),
    },
    students: names.map((name, index) => ({
      student_id: `student_${index}`,
      student_name: name,
      student_number: `20240${index + 1}01${String(index + 8).padStart(2, "0")}`,
      submission_status: index < Math.min(submitted, names.length) ? (index === 2 ? "late" : "submitted") : "not_submitted",
      submitted_at: index < submitted ? "2026-07-30T20:18:00+08:00" : null,
      score: index < Math.max(0, submitted - 8) ? 86 + index : null,
    })),
  };
}

export async function getAdminUsers(useMock, filters = {}) {
  if (!useMock) {
    const { data } = await client.get("/auth/admin/users", { params: { ...filters, page_size: 100 } });
    return data;
  }
  await delay();
  let items = mock().users;
  if (filters.role) items = items.filter((item) => item.role === filters.role);
  if (filters.is_active !== undefined && filters.is_active !== "") {
    items = items.filter((item) => item.is_active === filters.is_active);
  }
  if (filters.query) {
    const q = filters.query.toLowerCase();
    items = items.filter((item) => [item.display_name, item.username, item.student_number, item.teacher_number].some((value) => value?.toLowerCase().includes(q)));
  }
  return { items, total: items.length, page: 1, page_size: 100 };
}

export async function createAdminUser(useMock, payload) {
  if (!useMock) {
    const { data } = await client.post("/auth/admin/users", payload);
    return data;
  }
  await delay(420);
  const data = mock();
  if (data.users.some((item) => item.username === payload.username)) throw new Error("用户名已存在");
  const item = { id: nowId("usr"), ...payload, password: undefined, is_active: true, created_at: new Date().toISOString() };
  data.users.unshift(item);
  saveMockPortal(data);
  return item;
}

export async function updateAdminUser(useMock, userId, payload) {
  if (!useMock) {
    const { data } = await client.patch(`/auth/admin/users/${userId}`, payload);
    return data;
  }
  await delay();
  const data = mock();
  const item = data.users.find((entry) => entry.id === userId);
  if (!item) throw new Error("账号不存在");
  Object.assign(item, payload);
  saveMockPortal(data);
  return item;
}

export async function getActivities(useMock, filters = {}) {
  if (!useMock) {
    const { data } = await client.get("/activities", { params: { ...filters, page_size: 100 } });
    return data;
  }
  await delay();
  let items = mock().activities;
  if (filters.status) items = items.filter((item) => item.status === filters.status);
  if (filters.query) items = items.filter((item) => `${item.title}${item.summary}${item.location}`.includes(filters.query));
  return { items, total: items.length, page: 1, page_size: 100 };
}

export async function createActivity(useMock, payload) {
  if (!useMock) {
    const { data } = await client.post("/admin/activities", payload);
    return data;
  }
  await delay(420);
  const data = mock();
  const item = { id: nowId("act"), ...payload, published_at: payload.status === "published" ? new Date().toISOString() : null, created_at: new Date().toISOString() };
  data.activities.unshift(item);
  saveMockPortal(data);
  return item;
}

export async function updateActivityStatus(useMock, activityId, status) {
  if (!useMock) {
    const action = status === "published" ? "publish" : "close";
    const { data } = await client.post(`/admin/activities/${activityId}/${action}`);
    return data;
  }
  await delay();
  const data = mock();
  const item = data.activities.find((entry) => entry.id === activityId);
  if (!item) throw new Error("活动不存在");
  item.status = status;
  if (status === "published") item.published_at = new Date().toISOString();
  saveMockPortal(data);
  return item;
}

export async function getAdminOverview(useMock) {
  if (!useMock) {
    const [users, activities, courses] = await Promise.all([
      getAdminUsers(false),
      getActivities(false),
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
  await delay();
  const data = mock();
  return {
    user_count: data.users.length,
    student_count: data.users.filter((item) => item.role === "student").length,
    teacher_count: data.users.filter((item) => item.role === "teacher").length,
    inactive_count: data.users.filter((item) => !item.is_active).length,
    activity_count: data.activities.length,
    published_activity_count: data.activities.filter((item) => item.status === "published").length,
    course_count: data.courses.length,
    recent_users: data.users.slice(0, 5),
    recent_activities: data.activities.slice(0, 4),
  };
}
