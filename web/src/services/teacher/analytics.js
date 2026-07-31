import client from "../api";

export async function getTeacherAnalytics(params = {}) {
  const { data } = await client.get("/teacher/analytics", { params });
  return data;
}