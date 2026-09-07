import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import * as api from "../data/api.js";
import { itemsOf } from "../data/contracts.js";
import { Icon } from "../components/Icon.jsx";
import SummerNavDock from "../components/study/SummerNavDock.jsx";
import { useAmbientSound } from "../features/study/ambientSound.js";

const SCENES = ["rain", "snow", "cloud"];
const sceneLabel = { rain: "雨景", snow: "雪景", cloud: "暖云" };
const errorText = (error, fallback) => error?.response?.data?.detail || error?.message || fallback;
const isDone = (task) => ["completed", "done", "closed"].includes(String(task?.status || "").toLowerCase());
const minutesOf = (session) => Math.max(0, Math.round(Number(session?.duration_seconds || 0) / 60));
const dateLabel = (value) => value ? new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric" }).format(new Date(value)) : "待安排";

function useStudyScene() {
  const [scene, setScene] = useState(() => {
    const value = window.localStorage.getItem("campus_study_scene");
    return SCENES.includes(value) ? value : "rain";
  });
  const audio = useAmbientSound(scene);
  const select = (next) => { setScene(next); window.localStorage.setItem("campus_study_scene", next); };
  return { scene, select, audio };
}

function StudyShell({ eyebrow, title, description, scene, onSelectScene, audio, children }) {
  return <main className="study-summer-subpage" data-study-scene={scene}>
    <div className="study-summer-subpage__backdrop" aria-hidden="true" />
    <div className="study-summer-subpage__shade" aria-hidden="true" />
    <header className="study-summer-subpage__header">
      <div><span className="study-summer-eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>
      <div className="study-summer-subpage__scene-picker" aria-label="场景切换">
        {SCENES.map((item) => <button key={item} type="button" className={scene === item ? "is-active" : ""} onClick={() => onSelectScene(item)}>{sceneLabel[item]}<small>{item === "rain" ? "森林回声" : item === "snow" ? "安静一点" : "暖融静谧"}</small></button>)}
      </div>
    </header>
    <div className="study-summer-subpage__content">{children}</div>
    <SummerNavDock sceneAudio={audio} />
  </main>;
}

function Stat({ label, value, unit = "", icon = "PhSparkle" }) {
  return <div className="study-sub-stat"><span><Icon name={icon} size={17} /></span><div><small>{label}</small><strong>{value}<em>{unit}</em></strong></div></div>;
}

function LoadingState({ error, onRetry }) {
  if (error) return <div className="study-sub-empty"><Icon name="PhWarningCircle" size={28} /><p>{error}</p><button type="button" onClick={onRetry}>重新加载</button></div>;
  return <div className="study-sub-empty"><span className="loading-orb" /><p>正在整理你的学习空间…</p></div>;
}

export function PlansPage() {
  const { scene, select, audio } = useStudyScene();
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [title, setTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const load = async () => { setLoading(true); setError(""); try { setTasks(itemsOf(await api.getTasks())); } catch (err) { setError(errorText(err, "计划加载失败")); } finally { setLoading(false); } };
  useEffect(() => { void load(); }, []);
  async function addTask(event) { event.preventDefault(); if (!title.trim() || saving) return; setSaving(true); try { const created = await api.createTask({ title: title.trim(), source_name: "学习陪伴计划" }); setTasks((current) => [created, ...current]); setTitle(""); } catch (err) { setError(errorText(err, "计划保存失败")); } finally { setSaving(false); } }
  async function toggleTask(task) { try { const updated = await api.completeTask(task.id, !isDone(task)); setTasks((current) => current.map((item) => item.id === task.id ? { ...item, ...updated, status: updated?.status || (!isDone(task) ? "completed" : "pending") } : item)); } catch (err) { setError(errorText(err, "计划状态更新失败")); } }
  async function removeTask(task) { if (!window.confirm(`删除“${task.title}”？`)) return; try { await api.deleteTask(task.id); setTasks((current) => current.filter((item) => item.id !== task.id)); } catch (err) { setError(errorText(err, "计划删除失败")); } }
  const completed = tasks.filter(isDone).length;
  return <StudyShell eyebrow="Learning map" title="计划" description="把长期目标收拢成清晰、能执行的下一步。" scene={scene} onSelectScene={select} audio={audio}>
    <section className="study-sub-stats"><Stat label="全部计划" value={tasks.length} unit="项" icon="PhListChecks" /><Stat label="完成进度" value={tasks.length ? Math.round(completed / tasks.length * 100) : 0} unit="%" icon="PhChartLineUp" /><Stat label="已完成任务" value={completed} unit={`/ ${tasks.length}`} icon="PhCheckCircle" /></section>
    <section className="study-sub-panel study-plan-board">
      <div className="study-sub-panel__heading"><div><span className="study-sub-kicker">NEXT STEPS</span><h2>今天继续推进</h2><p>计划直接使用主项目的个人任务接口，和学习陪伴首页的待办保持同步。</p></div><Link className="study-sub-link" to="/study">回到专注室 <Icon name="PhArrowUpRight" size={15} /></Link></div>
      <form className="study-sub-create" onSubmit={addTask}><Icon name="PhPlus" size={18} /><input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="写下一个可以马上开始的步骤…" aria-label="新建学习计划" /><button type="submit" disabled={saving || !title.trim()}>{saving ? "保存中" : "加入计划"}</button></form>
      {loading ? <LoadingState /> : error ? <LoadingState error={error} onRetry={load} /> : <div className="study-plan-list">{tasks.length ? tasks.map((task) => <article className={`study-plan-row${isDone(task) ? " is-done" : ""}`} key={task.id}><button className="study-plan-check" type="button" aria-label={isDone(task) ? "恢复计划" : "完成计划"} onClick={() => void toggleTask(task)}><Icon name={isDone(task) ? "PhCheckCircle" : "PhCircle"} size={20} weight={isDone(task) ? "fill" : "regular"} /></button><div><strong>{task.title || "未命名计划"}</strong><small>{task.deadline ? `截止 ${dateLabel(task.deadline)}` : task.source_name || "学习陪伴计划"}</small></div><button className="study-plan-delete" type="button" aria-label={`删除 ${task.title || "计划"}`} onClick={() => void removeTask(task)}><Icon name="PhTrash" size={16} /></button></article>) : <div className="study-sub-empty"><Icon name="PhFlag" size={30} /><p>还没有计划，从一个明确的目标开始。</p></div>}</div>}
    </section>
  </StudyShell>;
}

export function DocsPage() {
  const { scene, select, audio } = useStudyScene();
  const navigate = useNavigate();
  const [documents, setDocuments] = useState([]);
  const [courses, setCourses] = useState([]);
  const [selected, setSelected] = useState(null);
  const [courseDetail, setCourseDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => { Promise.all([api.getKnowledgeDocuments().catch(() => []), api.getCourses().catch(() => [])]).then(([docs, courseList]) => { setDocuments(itemsOf(docs)); setCourses(itemsOf(courseList)); }).catch((err) => setError(errorText(err, "阅读内容加载失败"))).finally(() => setLoading(false)); }, []);
  async function openCourse(course) { setSelected(course); setCourseDetail(null); try { setCourseDetail(await api.getCourseDetail(course.id)); } catch (err) { setError(errorText(err, "课程阅读内容加载失败")); } }
  const resources = itemsOf(courseDetail?.remoteContent);
  return <StudyShell eyebrow="Reading room" title="阅读" description="把课程资料、校内文档和下一次要读的内容，放在同一个安静入口。" scene={scene} onSelectScene={select} audio={audio}>
    <div className="study-reading-grid">
      <section className="study-sub-panel"><div className="study-sub-panel__heading"><div><span className="study-sub-kicker">KNOWLEDGE BASE</span><h2>校内资料</h2><p>来自主项目知识库的可检索文档。</p></div><span className="study-sub-count">{documents.length} 篇</span></div>{loading ? <LoadingState /> : <div className="study-doc-list">{documents.length ? documents.map((doc) => <article key={doc.document_id || doc.id} className="study-doc-row"><span className="study-doc-icon"><Icon name="PhFileText" size={18} /></span><div><strong>{doc.title || doc.original_filename || "未命名资料"}</strong><small>{doc.source_department || doc.source_type || "学习资料"} · {doc.updated_at ? dateLabel(doc.updated_at) : "已收录"}</small></div><Icon name="PhArrowUpRight" size={16} /></article>) : <div className="study-sub-empty"><Icon name="PhBookOpen" size={30} /><p>知识库还没有资料，先从课程阅读开始。</p></div>}</div>}</section>
      <section className="study-sub-panel"><div className="study-sub-panel__heading"><div><span className="study-sub-kicker">COURSE READING</span><h2>课程阅读</h2><p>打开课程后可查看真实课程内容与资料。</p></div><span className="study-sub-count">{courses.length} 门</span></div><div className="study-course-list">{courses.length ? courses.map((course) => <button type="button" className={`study-course-row${selected?.id === course.id ? " is-active" : ""}`} key={course.id} onClick={() => void openCourse(course)}><span>{course.name || course.title || "未命名课程"}</span><Icon name="PhArrowRight" size={16} /></button>) : <div className="study-sub-empty"><p>暂无课程数据</p></div>}</div></section>
    </div>
    {selected && <section className="study-sub-panel study-reading-detail"><div className="study-sub-panel__heading"><div><span className="study-sub-kicker">NOW READING</span><h2>{selected.name || selected.title}</h2><p>{resources.length ? `${resources.length} 个课程资料` : "课程暂无可展开的阅读资料"}</p></div><button type="button" className="study-sub-link-button" onClick={() => navigate(`/courses/${selected.id}`)}>打开课程详情 <Icon name="PhArrowUpRight" size={15} /></button></div>{resources.length ? <div className="study-resource-grid">{resources.map((item) => <article className="study-resource-card" key={item.id || item.resource_id || item.title}><Icon name="PhArticle" size={20} /><strong>{item.title || item.name || "课程资料"}</strong><small>{item.type || item.resource_type || "阅读材料"}</small></article>)}</div> : <div className="study-sub-empty study-sub-empty--inline"><Icon name="PhBookOpen" size={26} /><p>可以先进入课程详情查看公告、作业和课程资料。</p></div>}</section>}
  </StudyShell>;
}

export function StatisticsPage() {
  const { scene, select, audio } = useStudyScene();
  const [sessions, setSessions] = useState([]);
  const [checkins, setCheckins] = useState({ items: [] });
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = async () => { setLoading(true); setError(""); try { const [sessionList, checkinSummary, taskList] = await Promise.all([api.getStudySessions(), api.getStudyCheckins(), api.getTasks()]); setSessions(itemsOf(sessionList)); setCheckins(checkinSummary || { items: [] }); setTasks(itemsOf(taskList)); } catch (err) { setError(errorText(err, "学习统计加载失败")); } finally { setLoading(false); } };
  useEffect(() => { void load(); }, []);
  const completedSessions = useMemo(() => sessions.filter((item) => item.status === "completed"), [sessions]);
  const totalMinutes = completedSessions.reduce((total, item) => total + minutesOf(item), 0);
  const completedTasks = tasks.filter(isDone).length;
  const checkinCount = Number(checkins.total || checkins.items?.length || 0);
  const trend = useMemo(() => Array.from({ length: 7 }, (_, index) => { const date = new Date(); date.setHours(0, 0, 0, 0); date.setDate(date.getDate() - (6 - index)); const key = date.toISOString().slice(0, 10); const minutes = completedSessions.filter((item) => String(item.started_at || "").slice(0, 10) === key).reduce((sum, item) => sum + minutesOf(item), 0); return { label: new Intl.DateTimeFormat("zh-CN", { weekday: "short" }).format(date).replace("周", ""), minutes }; }), [completedSessions]);
  return <StudyShell eyebrow="Focus archive" title="主页" description="看见每一次出现、完成和继续。学习陪伴把专注记录整理成可回看的节奏。" scene={scene} onSelectScene={select} audio={audio}>
    {loading ? <LoadingState /> : error ? <LoadingState error={error} onRetry={load} /> : <><section className="study-sub-stats"><Stat label="累计专注" value={totalMinutes} unit="分钟" icon="PhClock" /><Stat label="完成会话" value={completedSessions.length} unit="次" icon="PhCheckCircle" /><Stat label="学习打卡" value={checkinCount} unit="天" icon="PhCalendar" /><Stat label="任务完成率" value={tasks.length ? Math.round(completedTasks / tasks.length * 100) : 0} unit="%" icon="PhChartLineUp" /></section><div className="study-stat-grid"><section className="study-sub-panel"><div className="study-sub-panel__heading"><div><span className="study-sub-kicker">LAST 7 DAYS</span><h2>专注趋势</h2><p>完成的学习会话按开始日期累计。</p></div><strong className="study-panel-number">{totalMinutes}<em> min</em></strong></div><div className="study-stat-chart" aria-label="近七日专注趋势">{trend.map((item) => <div key={item.label}><span style={{ height: `${Math.max(item.minutes ? 12 : 3, Math.round(item.minutes / Math.max(...trend.map((value) => value.minutes), 1) * 100))}%` }} /><small>{item.label}</small><b>{item.minutes || ""}</b></div>)}</div></section><section className="study-sub-panel"><div className="study-sub-panel__heading"><div><span className="study-sub-kicker">RECENT RECORDS</span><h2>最近记录</h2><p>每一次完成都会留下轨迹。</p></div><Link className="study-sub-link" to="/study">开始一次专注 <Icon name="PhArrowUpRight" size={15} /></Link></div><div className="study-record-list">{completedSessions.slice(0, 6).map((item) => <article key={item.id}><span><Icon name="PhCheckCircle" size={17} /></span><div><strong>{item.goal || "一次学习陪伴"}</strong><small>{dateLabel(item.started_at)} · {minutesOf(item)} 分钟</small></div></article>)}{!completedSessions.length && <div className="study-sub-empty study-sub-empty--inline"><Icon name="PhTimer" size={26} /><p>完成第一次专注后，这里会显示你的记录。</p></div>}</div></section></div></>}
  </StudyShell>;
}

export default function StudySubpages() {
  const { pathname } = useLocation();
  if (pathname.startsWith("/docs")) return <DocsPage />;
  if (pathname.startsWith("/statistics")) return <StatisticsPage />;
  return <PlansPage />;
}
