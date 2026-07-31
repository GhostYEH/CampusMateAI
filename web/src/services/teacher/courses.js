import client from "../api";

export async function listCourses(params = {}) {
  const { data } = await client.get("/courses", {
    params: { page_size: 100, ...params },
  });
  return data;
}

export async function getCourse(courseId) {
  const { data } = await client.get(`/courses/${courseId}`);
  return data;
}

export async function createCourse(payload) {
  const { data } = await client.post("/courses", payload);
  return data;
}

export async function updateCourse(courseId, payload) {
  const { data } = await client.patch(`/courses/${courseId}`, payload);
  return data;
}