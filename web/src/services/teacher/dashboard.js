import client from "../api";

export async function getTeacherDashboard() {
  const { data } = await client.get("/dashboard/teacher");
  return data;
}

export async function getTeacherToday() {
  const { data } = await client.get("/teacher/today");
  return data;
}