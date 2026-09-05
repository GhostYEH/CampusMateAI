import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import * as api from "../data/api.js";
import { itemsOf, normalizeNotice } from "../data/contracts.js";
import { formatDateTime } from "../utils/date.js";
import { AsyncState, BackLink, Button, LinkButton, Modal, PageFrame, Panel, SectionHeading, StatCard } from "../components/Primitives.jsx";
import { Icon } from "../components/Icon.jsx";

const errorText = (error, fallback = "操作失败，请稍后重试") => error?.response?.data?.detail || error?.response?.data?.message || error?.message || fallback;
const dateText = (value, fallback = "时间待定") => formatDateTime(value, { dateStyle: "medium", timeStyle: "short" }, fallback);
const dayText = (value) => formatDateTime(value, { month: "numeric", day: "numeric", weekday: "short" }, "日期待定");

function useResource(loader, deps = []) {
  const [state, setState] = useState({ data: null, loading: true, error: "" });
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let alive = true;
    setState((current) => ({ ...current, loading: true, error: "" }));
    Promise.resolve().then(loader).then((data) => alive && setState({ data, loading: false, error: "" })).catch((error) => alive && setState({ data: null, loading: false, error: errorText(error, "加载失败，请稍后重试") }));
    return () => { alive = false; };
    // The explicit dependencies are the resource identity; reload is represented by version.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version]);
  return { ...state, reload: () => setVersion((current) => current + 1) };
}

function PageNotice({ message, tone = "info" }) {
  return message ? <div className={`page-notice notice-${tone}`} role={tone === "error" ? "alert" : "status"}><Icon name={tone === "error" ? "PhWarningCircle" : "PhInfo"} size={17} />{message}</div> : null;
}

function ListRow({ icon = "PhCircle", title, detail, meta, to, onClick, tone = "blue", children }) {
  const content = <><span className={`row-icon tone-${tone}`}><Icon name={icon} size={18} /></span><span className="row-copy"><strong>{title}</strong><small>{detail}</small></span>{meta && <span className="row-meta">{meta}</span>}{children}{to && <Icon name="PhCaretRight" size={16} />}</>;
  return to ? <Link className="list-row" to={to}>{content}</Link> : <button type="button" className="list-row" onClick={onClick}>{content}</button>;
}

function noticeSourceUrl(item) {
  if (item?.kind !== "unified" || !item.source_url) return null;
  try { const url = new URL(item.source_url, window.location.href); return ["http:", "https:"].includes(url.protocol) ? url.href : null; } catch { return null; }
}

export function NotificationsPage() {
  const resource = useResource(() => api.getNotices(), []);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState(""); const [source, setSource] = useState("all"); const [readFilter, setReadFilter] = useState("all"); const [expanded, setExpanded] = useState(null); const [extractText, setExtractText] = useState(""); const [extracting, setExtracting] = useState(false); const [extracted, setExtracted] = useState(null); const [saving, setSaving] = useState(false); const [notice, setNotice] = useState("");
  useEffect(() => { const initial = searchParams.get("extract"); if (initial) setExtractText(initial); }, [searchParams]);
  const items = itemsOf(resource.data).map(normalizeNotice);
  const sources = [...new Set(items.map((item) => item.source).filter(Boolean))];
  const filtered = items.filter((item) => (source === "all" || item.source === source) && (readFilter === "all" || !item.has_read) && `${item.title || ""} ${item.content || ""}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
  async function toggle(item) { setExpanded((current) => current === item.id ? null : item.id); if (item.kind === "announcement" && !item.has_read) { try { await api.markAnnouncementRead(item.id); item.has_read = true; resource.reload(); } catch { setNotice("通知已打开，但已读状态同步失败"); } } }
  function open(item) { const url = noticeSourceUrl(item); if (url) { window.open(url, "_blank", "noopener,noreferrer"); return; } if (item.kind === "announcement") { navigate(`/announcements/${item.id}`); return; } setNotice("这条通知暂无可打开的原始链接"); }
  async function extract() { if (!extractText.trim() || extracting) return; setExtracting(true); setExtracted(null); try { setExtracted(await api.extractNotice(extractText.trim())); } catch (error) { setExtracted({ error: errorText(error, "提取失败，请检查通知内容") }); } finally { setExtracting(false); } }
  async function saveTask() { const task = extracted?.tasks?.[0] || extracted; const title = task?.task || task?.title; if (!title || saving) return; setSaving(true); try { await api.createTask({ title, description: task.source_text || extractText, deadline: task.deadline, materials: (task.materials || []).map((item) => item.name || item), submission_method: task.submission_method, location: task.location, source_name: task.source_name || "校园通知", source_text: extractText, priority: task.importance === "high" || task.importance === "urgent" ? "high" : "medium", importance: task.importance || "unknown" }); setNotice("已保存为个人待办"); } catch (error) { setNotice(errorText(error, "保存待办失败")); } finally { setSaving(false); } }
  return <PageFrame eyebrow="Inbox / Notices" title="通知整理" description="把课程公告和校园消息集中到一个可回看的列表里。" actions={<><Button variant="secondary" icon="PhArrowClockwise" onClick={resource.reload}>刷新通知</Button><LinkButton to="/profile/chaoxing" variant="secondary" icon="PhGraduationCap">管理学习通</LinkButton></>}><section className="asset-page-hero notice-asset-hero"><div><span className="eyebrow">CAMPUS INBOX</span><h2>重要消息，一眼就能找到</h2><p>确认通知、提取截止时间，再把行动项交给任务清单。</p></div><img src="/assets/campusmate-notice-illustration.png" alt="通知整理插画" /></section><div className="notice-toolbar filter-bar"><label className="search-field-wrap"><Icon name="PhMagnifyingGlass" size={17} /><input className="search-field" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索通知标题或内容" /></label><select value={source} onChange={(event) => setSource(event.target.value)}><option value="all">全部来源</option>{sources.map((item) => <option key={item} value={item}>{item}</option>)}</select><select value={readFilter} onChange={(event) => setReadFilter(event.target.value)}><option value="all">全部通知</option><option value="unread">仅看未读</option></select></div><AsyncState loading={resource.loading} error={resource.error} empty={!filtered.length ? "暂时没有匹配通知" : null} onRetry={resource.reload}><Panel className="list-panel reveal"><div className="list-stack">{filtered.map((item) => <article className={`notice-row ${item.has_read ? "" : "unread"}`} key={`${item.kind}-${item.id}`}><button className="list-row" onClick={() => toggle(item)}><span className="row-icon tone-orange"><Icon name={item.has_read ? "PhEnvelopeOpen" : "PhEnvelope"} size={18} /></span><span className="row-copy"><strong>{item.title || "校园通知"}</strong><small>{item.source || "校园通知"} · {item.kind === "unified" ? "统一通知" : "课程公告"}</small></span><span className="row-meta">{dateText(item.time || item.published_at || item.created_at, "刚刚")}</span><Icon name={expanded === item.id ? "PhCaretDown" : "PhCaretRight"} size={16} /></button>{expanded === item.id && <div className="notice-expand-body"><p>{item.content || "暂无通知正文"}</p><div className="notice-expand-actions"><Button variant="quiet" icon="PhArrowUpRight" onClick={() => open(item)}>{item.kind === "unified" ? "打开原始通知" : "查看完整详情"}</Button><Button variant="quiet" icon="PhRobot" onClick={() => navigate(`/counselor?prompt=${encodeURIComponent(`请帮我处理这条通知：${item.title || "校园通知"}\n${item.content || ""}`)}`)}>交给 AI</Button></div></div>}</article>)}</div></Panel></AsyncState><Panel className="notice-extract-panel"><SectionHeading title="从通知生成待办" detail="提取结果仅作为草稿，保存前请核对截止时间和提交方式。" /><textarea value={extractText} onChange={(event) => setExtractText(event.target.value)} rows="6" maxLength="20000" placeholder="粘贴教务处、学院或学生工作部门的通知原文" /><div className="form-footer"><Button disabled={extracting || !extractText.trim()} onClick={extract}>{extracting ? "正在提取…" : "开始提取"}</Button>{(extracted?.tasks?.length || extracted?.title || extracted?.task) && <Button variant="secondary" disabled={saving} onClick={saveTask}>{saving ? "保存中…" : "保存为待办"}</Button>}</div>{extracted?.error && <PageNotice message={extracted.error} tone="error" />}{extracted && !extracted.error && <div className="extract-result"><strong>{extracted.tasks?.[0]?.task || extracted.task || extracted.title || "已完成提取"}</strong><small>{extracted.tasks?.[0]?.deadline || extracted.deadline || "未识别截止时间"}</small></div>}</Panel><PageNotice message={notice} /></PageFrame>;
}

const blankExam = () => ({ course_name: "", exam_date: "", start_time: "", end_time: "", location: "", seat_number: "", exam_type: "", reminder_enabled: true, notes: "" });
function ExamForm({ form, setForm, onSubmit, submitLabel = "保存考试" }) { const set = (key, value) => setForm((current) => ({ ...current, [key]: value })); return <form className="form-grid" onSubmit={onSubmit}><div className="field full"><label>课程名称</label><input required value={form.course_name} onChange={(event) => set("course_name", event.target.value)} /></div><div className="field"><label>考试日期</label><input required type="date" value={form.exam_date} onChange={(event) => set("exam_date", event.target.value)} /></div><div className="field"><label>考试类型</label><input value={form.exam_type} placeholder="例如：期末考试" onChange={(event) => set("exam_type", event.target.value)} /></div><div className="field"><label>开始时间</label><input type="time" value={form.start_time} onChange={(event) => set("start_time", event.target.value)} /></div><div className="field"><label>结束时间</label><input type="time" value={form.end_time} onChange={(event) => set("end_time", event.target.value)} /></div><div className="field"><label>地点</label><input value={form.location} onChange={(event) => set("location", event.target.value)} /></div><div className="field"><label>座位号</label><input value={form.seat_number} onChange={(event) => set("seat_number", event.target.value)} /></div><div className="field full"><label>备注</label><textarea rows="3" value={form.notes} onChange={(event) => set("notes", event.target.value)} /></div><label className="check-label field full"><input type="checkbox" checked={form.reminder_enabled} onChange={(event) => set("reminder_enabled", event.target.checked)} />保存提醒偏好</label><div className="form-footer field full"><Button>{submitLabel}</Button></div></form>; }

function examStartAt(exam) {
  if (!exam?.exam_date) return null;
  const date = String(exam.exam_date).slice(0, 10);
  const time = String(exam.start_time || "00:00");
  const value = new Date(`${date}T${time.length === 5 ? `${time}:00` : time}`);
  return Number.isNaN(value.getTime()) ? null : value.getTime();
}

function countdownLabel(exam, now = Date.now()) {
  const start = examStartAt(exam);
  if (start === null) return "时间待定";
  const minutes = Math.max(0, Math.floor((start - now) / 60000));
  if (start <= now) return "已开始/已结束";
  const days = Math.floor(minutes / 1440);
  const hours = Math.floor((minutes % 1440) / 60);
  const rest = minutes % 60;
  return days ? `${days}天 ${hours}小时` : hours ? `${hours}小时 ${rest}分` : `${rest}分钟`;
}

function ExamCountdown({ exam }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 60000); return () => window.clearInterval(timer); }, []);
  return <small className="exam-countdown">{countdownLabel(exam, now)}</small>;
}

export function ExamsPage() {
  const resource = useResource(() => api.getExams(), []); const navigate = useNavigate(); const [open, setOpen] = useState(false); const [form, setForm] = useState(blankExam()); const [notice, setNotice] = useState(""); const [now, setNow] = useState(Date.now());
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 60000); return () => window.clearInterval(timer); }, []);
  const items = itemsOf(resource.data).slice().sort((a, b) => `${a.exam_date} ${a.start_time || ""}`.localeCompare(`${b.exam_date} ${b.start_time || ""}`)); const upcoming = items.filter((item) => { const start = examStartAt(item); return start !== null && start > now; }); const past = items.filter((item) => !upcoming.includes(item));
  async function save(event) { event.preventDefault(); try { await api.saveExam(form); setOpen(false); setForm(blankExam()); setNotice("考试安排已保存"); resource.reload(); } catch (error) { setNotice(errorText(error)); } }
  async function remove(id) { if (!window.confirm("确认删除这条考试安排吗？")) return; try { await api.deleteExam(id); setNotice("考试安排已删除"); resource.reload(); } catch (error) { setNotice(errorText(error)); } }
  return <PageFrame eyebrow="Academic / Exams" title="考试安排" description="把重要考试放进一个可回看的时间轴，提前为复习留出空间。" actions={<><Button variant="secondary" icon="PhArrowClockwise" onClick={resource.reload}>刷新</Button><Button icon="PhPlus" onClick={() => setOpen(true)}>添加考试</Button></>}>
    <PageNotice message={notice} tone={notice.includes("失败") ? "error" : "info"} />
    <div className="stat-grid"><StatCard label="全部考试" value={items.length} detail="已保存安排" icon="PhCalendarCheck" tone="blue" /><StatCard label="待参加" value={upcoming.length} detail="按开始时间计算" icon="PhTimer" tone="orange" /><StatCard label="最近一场" value={upcoming[0] ? countdownLabel(upcoming[0], now) : "—"} detail={upcoming[0]?.course_name || "暂无待参加考试"} icon="PhFlag" tone="violet" /></div>
    <AsyncState loading={resource.loading} error={resource.error} empty={!items.length ? "还没有考试安排" : null} onRetry={resource.reload}><Panel className="timeline-panel reveal"><div className="timeline">{items.map((item) => <div className="timeline-item" key={item.id}><button className="timeline-item-main" onClick={() => navigate(`/exams/${item.id}`)}><span className="timeline-date">{dayText(item.exam_date)}<small>{item.start_time || "时间待定"}{item.end_time ? ` - ${item.end_time}` : ""}</small><ExamCountdown exam={item} /></span><span className="timeline-dot" /><span className="timeline-copy"><strong>{item.course_name || "考试"}</strong><small>{item.exam_type || "考试"} · {item.location || "地点待定"} · 座位 {item.seat_number || "待定"}</small></span><Icon name="PhCaretRight" size={16} /></button><Button variant="danger" onClick={() => remove(item.id)} aria-label={`删除${item.course_name || "考试"}`}>删除</Button></div>)}</div>{past.length > 0 && <p className="muted-copy exam-history-note">已显示 {past.length} 场已开始或已结束的考试，历史安排仍可打开查看。</p>}</Panel></AsyncState>
    {open && <Modal title="添加考试" onClose={() => setOpen(false)}><ExamForm form={form} setForm={setForm} onSubmit={save} /></Modal>}
  </PageFrame>;
}

function useExam(examId) { const resource = useResource(() => api.getExams(), [examId]); const exam = itemsOf(resource.data).find((item) => String(item.id) === String(examId)) || null; return { ...resource, exam }; }
export function ExamEditPage() { const { examId } = useParams(); const navigate = useNavigate(); const resource = useExam(examId); const [form, setForm] = useState(null); const [error, setError] = useState(""); useEffect(() => { if (resource.exam && !form) setForm({ ...blankExam(), ...resource.exam }); }, [resource.exam, form]); async function save(event) { event.preventDefault(); try { await api.saveExam(form, examId); navigate(`/exams/${examId}`); } catch (cause) { setError(errorText(cause)); } } return <PageFrame eyebrow="Academic / Edit" title="编辑考试" actions={<BackLink to={`/exams/${examId}`}>返回详情</BackLink>}><PageNotice message={error} tone="error" /><AsyncState loading={resource.loading} error={resource.error} onRetry={resource.reload}>{form && <Panel><ExamForm form={form} setForm={setForm} onSubmit={save} submitLabel="保存修改" /></Panel>}</AsyncState></PageFrame>; }


