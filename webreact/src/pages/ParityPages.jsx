import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import * as api from "../data/api.js";
import { itemsOf } from "../data/contracts.js";
import { courseProgress, examDetailFields } from "../data/alignment.js";
import { AsyncState, BackLink, Button, Modal, PageFrame, Panel, SectionHeading } from "../components/Primitives.jsx";
import { Icon } from "../components/Icon.jsx";
import { CourseCard } from "../components/CourseCard.jsx";
import { formatDateTime } from "../utils/date.js";

const list = itemsOf;
const dateText = (value) => formatDateTime(value, { dateStyle: "medium", timeStyle: "short" }, "时间待定");

export function CoursesParityPage() {
  const [data, setData] = useState([[], []]); const [loading, setLoading] = useState(true); const [error, setError] = useState(""); const [query, setQuery] = useState(""); const [sort, setSort] = useState("name");
  async function load() { setLoading(true); setError(""); try { const [courses, assignments] = await Promise.all([api.getCourses(), api.getAssignments()]); setData([list(courses), list(assignments)]); } catch (err) { setError(err?.response?.data?.detail || err?.message || "课程加载失败，请重试。"); } finally { setLoading(false); } }
  useEffect(() => { load(); }, []);
  const [courses, assignments] = data;
  const visible = useMemo(() => courses.filter((course) => `${course.name || ""} ${course.code || ""} ${course.teacher_name || ""}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())).slice().sort((a, b) => sort === "updated" ? String(b.updated_at || "").localeCompare(String(a.updated_at || "")) : String(a.name || "").localeCompare(String(b.name || ""), "zh-CN")), [courses, query, sort]);
  return <PageFrame className="courses-page" eyebrow="Learning / Courses" title="我的课程" description="按课程整理公告、作业和学习资料，进入详情继续处理。" actions={<Button variant="secondary" icon="PhArrowClockwise" onClick={load}>刷新</Button>}>
    <div className="filter-bar"><label className="search-field-wrap"><Icon name="PhMagnifyingGlass" size={17} /><input className="search-field" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索课程名称、代码或教师" /></label><select aria-label="课程排序" value={sort} onChange={(event) => setSort(event.target.value)}><option value="name">按课程名称</option><option value="updated">按最近更新</option></select><span className="toolbar-count">共 {visible.length} 门课程</span></div>
    <AsyncState loading={loading} error={error} empty={!visible.length ? "暂时没有匹配的课程" : null} onRetry={load}><div className="course-grid reveal">{visible.map((course) => <CourseCard key={course.id} course={course} progress={courseProgress(course, assignments)} />)}</div></AsyncState>
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
