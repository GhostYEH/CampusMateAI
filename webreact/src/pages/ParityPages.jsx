import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import * as api from "../data/api.js";
import { itemsOf } from "../data/contracts.js";
import { examDetailFields } from "../data/alignment.js";
import { AsyncState, BackLink, Button, Modal, PageFrame, Panel, SectionHeading } from "../components/Primitives.jsx";
import { Icon } from "../components/Icon.jsx";
import OpenMAICHome from "../components/openmaic/OpenMAICHome.jsx";
import { describeFusionState, normalizeRecentItems } from "../features/openmaic/homeModel.js";
import {
  generationPreviewHref,
  quickAskRejection,
  shouldBindWorkspace,
} from "../features/openmaic/quickAskModel.js";
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
  // 快速询问的失败**只**影响输入区。它绝不能写进上面这个页级 error：那个 error
  // 由 AsyncState 消费，一旦被写上，整块课程内容都会被一张错误卡片替换掉——
  // 这正是"快速询问 503 之后连课程列表都没了"的成因。
  const [quickAskError, setQuickAskError] = useState(null);
  const [quickAskBusy, setQuickAskBusy] = useState(false);
  // 代次：课程切换与组件卸载都会 +1。迟到的响应据此作废，绝不把旧课程的
  // 工作台写到新课程页面上。
  const quickAskSeq = useRef(0);
  const aliveRef = useRef(true);

  // 注意 effect 体里必须把 alive 重新置回 true。React 18 的 StrictMode 在开发环境
  // 会跑一遍"挂载 → 卸载 → 再挂载"：只在 cleanup 里置 false，第二次挂载就再也回不到
  // true，结果是每次快速询问都在守卫处静默 return —— 请求成功（200/201），但既不跳转
  // 也不报错，按钮永远停在"正在准备…"。这个缺陷单测看不到，只有真实浏览器能暴露。
  useEffect(() => {
    aliveRef.current = true;
    return () => { aliveRef.current = false; quickAskSeq.current += 1; };
  }, []);

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

  /** 课程切换：作废在途的快速询问，并清掉上一次的局部错误。 */
  function handleCourseChange() {
    quickAskSeq.current += 1;
    setQuickAskBusy(false);
    setQuickAskError(null);
  }

  function openQuickAsk(query, courseId, extras = {}) {
    const rejection = quickAskRejection({ query, courseId, busy: quickAskBusy });
    if (rejection) {
      setQuickAskError({ message: rejection, retryable: false, fallbackLabel: "" });
      return;
    }
    ++quickAskSeq.current;
    setQuickAskError(null);

    // OpenMAIC 课程入口必须落到可持久化的工作台；不能用课程辅导页冒充成功。
    if (!shouldBindWorkspace(describeFusionState(fusion))) {
      setQuickAskError({
        kind: "unavailable",
        reason: "workspace_unavailable",
        retryable: true,
        message: "OpenMAIC 学习工作台暂时不可用，请稍后重试。",
        fallbackLabel: "",
      });
      return;
    }

    // 先进入和参考项目一致的生成预览；只有用户确认后才复用/创建工作台。
    setQuickAskBusy(false);
    navigate(generationPreviewHref(courseId, query, {
      mode: extras.mode,
      selectedRoleIds: extras.selectedRoleIds,
      webSearch: extras.webSearch,
    }), {
      // File 对象不能写入 URL，保留在本次 SPA 导航状态里，确认生成时继续传给工作台。
      state: {
        openmaicWebSearch: Boolean(extras.webSearch),
        openmaicAttachment: extras.attachment || null,
      },
    });
  }

  return <PageFrame className="courses-page" eyebrow="课程" title="学习内容" description="选择课程后直接提问，或创建一份可以继续编辑的学习内容。" actions={<Button variant="secondary" icon="PhArrowClockwise" onClick={load} disabled={loading}>{loading ? "同步中…" : "刷新"}</Button>}>
    <AsyncState loading={loading} error={error} empty={!courses.length ? "暂时没有已选课程" : null} onRetry={load}>
      <OpenMAICHome
        courses={courses}
        assignments={assignments}
        recentItems={recentItems}
        recentError={recentError}
        fusion={fusion}
        providerStatus={providerStatus}
        quickAskError={quickAskError}
        quickAskBusy={quickAskBusy}
        onQuickAsk={openQuickAsk}
        onCourseChange={handleCourseChange}
        onCreateContent={(courseId) => openQuickAsk("创建一份课程学习内容", courseId)}
      />
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
