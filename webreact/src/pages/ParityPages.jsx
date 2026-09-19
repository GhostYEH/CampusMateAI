import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import * as api from "../data/api.js";
import { itemsOf } from "../data/contracts.js";
import { examDetailFields } from "../data/alignment.js";
import { AsyncState, BackLink, Button, Modal, PageFrame, Panel, SectionHeading } from "../components/Primitives.jsx";
import { Icon } from "../components/Icon.jsx";
import OpenMAICHome from "../components/openmaic/OpenMAICHome.jsx";
import { formatDateTime } from "../utils/date.js";

const list = itemsOf;
const dateText = (value) => formatDateTime(value, { dateStyle: "medium", timeStyle: "short" }, "时间待定");
export function CoursesParityPage() {
  const navigate = useNavigate();
  const [courses, setCourses] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [recentClassrooms, setRecentClassrooms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [coursePayload, assignmentPayload] = await Promise.all([api.getCourses(), api.getAssignments()]);
      const nextCourses = list(coursePayload);
      setCourses(nextCourses);
      setAssignments(list(assignmentPayload));
      const historyResults = await Promise.allSettled(nextCourses.slice(0, 12).map(async (course) => ({
        courseId: course.id,
        ...(await api.listInteractiveClassrooms(course.id)),
      })));
      setRecentClassrooms(historyResults.filter((result) => result.status === "fulfilled").map((result) => result.value));
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "课程加载失败，请重试。");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  return <PageFrame className="courses-page" eyebrow="OpenMAIC / Courses" title="学习内容" description="在 CampusMate 课程上下文中创建、询问和继续学习内容。" actions={<Button variant="secondary" icon="PhArrowClockwise" onClick={load} disabled={loading}>{loading ? "同步中…" : "刷新"}</Button>}>
    <AsyncState loading={loading} error={error} empty={!courses.length ? "暂时没有已选课程" : null} onRetry={load}>
      <OpenMAICHome courses={courses} assignments={assignments} recentClassrooms={recentClassrooms.flatMap((history) => (history.items || []).map((item) => ({ ...item, courseId: history.courseId, courseName: courses.find((course) => String(course.id) === String(history.courseId))?.name }))) } onQuickAsk={(query, courseId) => navigate(`/counselor?course=${encodeURIComponent(courseId)}&prompt=${encodeURIComponent(query)}`)} onCreateContent={(courseId) => navigate(`/courses/${courseId}`)} />
    </AsyncState>
  </PageFrame>;
}

function countdown(exam, now) { const start = new Date(`${exam?.exam_date || ""}T${exam?.start_time || "00:00"}`).getTime(); if (!Number.isFinite(start)) return "时间待定"; const diff = start - now; if (diff <= 0) return "已开始或已结束"; const days = Math.floor(diff / 86400000); const hours = Math.floor(diff % 86400000 / 3600000); const minutes = Math.floor(diff % 3600000 / 60000); return days ? `${days} 天 ${hours} 小时` : `${hours} 小时 ${minutes} 分钟`; }

export function ExamDetailParityPage() {
  const { examId } = useParams(); const navigate = useNavigate(); const [now, setNow] = useState(Date.now()); const [items, setItems] = useState([]); const [loading, setLoading] = useState(true); const [error, setError] = useState("");
  async function load() { setLoading(true); setError(""); try { setItems(await api.getExams()); } catch (err) { setError(err?.response?.data?.detail || err?.message || "考试详情加载失败。"); } finally { setLoading(false); } }
  useEffect(() => { load(); const timer = window.setInterval(() => setNow(Date.now()), 60000); return () => window.clearInterval(timer); }, [examId]);
  const exam = items.find((value) => String(value.id) === String(examId)) || {};
  const missing = !loading && !error && exam.id == null;
  async function remove() { if (!window.confirm("确认删除这条考试安排吗？")) return; try { await api.deleteExam(examId); navigate("/exams", { replace: true }); } catch (err) { setError(err?.response?.data?.detail || err?.message || "删除考试失败，请稍后重试。"); } }
  return <PageFrame eyebrow="Academic / Exam Detail" title={exam.course_name || "考试详情"} description="考试时间、地点、座位和个人备注" actions={<><BackLink to="/exams">返回考试列表</BackLink><Button variant="secondary" icon="PhArrowClockwise" onClick={load}>刷新</Button><Button icon="PhPencil" onClick={() => navigate(`/exams/${examId}/edit`)} disabled={missing}>编辑</Button></>}><AsyncState loading={loading} error={error || (missing ? "未找到该考试记录。" : "")} onRetry={load}><div className="grid grid-2"><Panel><SectionHeading title="距离开考" /><div className="exam-countdown-card"><Icon name="PhTimer" size={24} /><strong>{countdown(exam, now)}</strong></div><div className="detail-grid"><div><span>日期</span><strong>{exam.exam_date || "待确认"}</strong></div><div><span>时间</span><strong>{exam.start_time || "待确认"}{exam.end_time ? ` - ${exam.end_time}` : ""}</strong></div><div><span>地点</span><strong>{exam.location || "待确认"}</strong></div><div><span>座位号</span><strong>{exam.seat_number || "待确认"}</strong></div>{examDetailFields(exam).map((field) => <div key={field.label}><span>{field.label}</span><strong>{field.value}</strong></div>)}</div><Button variant="danger" icon="PhTrash" onClick={remove}>删除考试</Button></Panel><Panel><SectionHeading title="复习提醒" /><p className="muted-copy">提前拆分复习内容，在学习陪伴中记录每次专注，避免把压力集中到考试前一天。</p><Button icon="PhPlay" onClick={() => navigate("/study")}>开始复习专注</Button></Panel></div></AsyncState></PageFrame>;
}
