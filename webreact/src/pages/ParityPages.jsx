import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import * as api from "../data/api.js";
import { itemsOf } from "../data/contracts.js";
import { examDetailFields } from "../data/alignment.js";
import { AsyncState, BackLink, Button, Modal, PageFrame, Panel, SectionHeading } from "../components/Primitives.jsx";
import { Icon } from "../components/Icon.jsx";
import OpenMAICHome from "../components/openmaic/OpenMAICHome.jsx";
import { normalizeRecentItems } from "../features/openmaic/homeModel.js";
import { formatDateTime } from "../utils/date.js";

const list = itemsOf;
const dateText = (value) => formatDateTime(value, { dateStyle: "medium", timeStyle: "short" }, "时间待定");

/** 最近内容的默认条数；上限由服务端固定（50）。 */
const RECENT_LIMIT = 20;

export function CoursesParityPage() {
  const navigate = useNavigate();
  const [courses, setCourses] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [recentItems, setRecentItems] = useState([]);
  const [recentError, setRecentError] = useState("");
  const [fusion, setFusion] = useState(null);
  const [providerStatus, setProviderStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    setRecentError("");
    try {
      const [coursePayload, assignmentPayload] = await Promise.all([api.getCourses(), api.getAssignments()]);
      setCourses(list(coursePayload));
      setAssignments(list(assignmentPayload));
      // 两个辅助请求各自独立降级：任一失败都不该让课程列表整页失败。
      const [recentResult, fusionResult, providerResult] = await Promise.allSettled([
        api.getOpenMAICRecent(RECENT_LIMIT),
        api.getOpenMAICFusionStatus(),
        api.getOpenMAICProviderStatus(),
      ]);
      if (recentResult.status === "fulfilled") {
        setRecentItems(normalizeRecentItems(recentResult.value));
      } else {
        setRecentItems([]);
        setRecentError("受管服务暂时不可用，请稍后重试。");
      }
      setFusion(fusionResult.status === "fulfilled" ? fusionResult.value : null);
      setProviderStatus(providerResult.status === "fulfilled" ? providerResult.value : null);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "课程加载失败，请重试。");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function openQuickAsk(query, courseId) {
    setError("");
    try {
      const payload = await api.listOpenMAICWorkspaces(courseId, { limit: 1 });
      let workspace = list(payload)[0];
      if (!workspace) {
        workspace = await api.createOpenMAICWorkspace(courseId, {
          name: "快速询问工作台",
          description: "由课程快速询问自动创建，用于继续追问与恢复学习上下文。",
          idempotencyKey: api.newIdempotencyKey(),
        });
      }
      if (!workspace?.id) throw new Error("工作台创建结果缺少标识");
      navigate(`/counselor?course=${encodeURIComponent(courseId)}&workspace=${encodeURIComponent(workspace.id)}&prompt=${encodeURIComponent(query)}`);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "无法创建课程工作台，请稍后重试。");
    }
  }

  return <PageFrame className="courses-page" eyebrow="OpenMAIC / Courses" title="学习内容" description="在 CampusMate 课程上下文中创建、询问和继续学习内容。" actions={<Button variant="secondary" icon="PhArrowClockwise" onClick={load} disabled={loading}>{loading ? "同步中…" : "刷新"}</Button>}>
    <AsyncState loading={loading} error={error} empty={!courses.length ? "暂时没有已选课程" : null} onRetry={load}>
      <OpenMAICHome courses={courses} assignments={assignments} recentItems={recentItems} recentError={recentError} fusion={fusion} providerStatus={providerStatus} onQuickAsk={openQuickAsk} onCreateContent={(courseId) => navigate(`/courses/${courseId}`)} />
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
