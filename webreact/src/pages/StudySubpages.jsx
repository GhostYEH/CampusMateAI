import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import * as api from "../data/api.js";
import { itemsOf, logApiError, userErrorMessage } from "../data/contracts.js";
import { Icon } from "../components/Icon.jsx";
import { Button } from "../components/Primitives.jsx";
import SummerNavDock from "../components/study/SummerNavDock.jsx";
import { useAmbientSound } from "../features/study/ambientSound.js";
import { saveStudyScene, STUDY_SCENES } from "../features/study/scenes.js";

const SCENE_KEYS = STUDY_SCENES.map((item) => item.key);
const isDone = (task) => ["completed", "done", "closed"].includes(String(task?.status || "").toLowerCase());
const minutesOf = (session) => Math.max(0, Math.round(Number(session?.duration_seconds || 0) / 60));
const dateLabel = (value) => value ? new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric" }).format(new Date(value)) : "待安排";

function useStudyScene() {
  const [scene, setScene] = useState(() => {
    const value = window.localStorage.getItem("campus_study_scene");
    return SCENE_KEYS.includes(value) ? value : "rain";
  });
  const audio = useAmbientSound(scene);
  const select = (next) => { setScene(saveStudyScene(next)); };
  return { scene, select, audio };
}

function StudyShell({ eyebrow, title, description, scene, onSelectScene, audio, children }) {
  return <main className="study-summer-subpage" data-study-scene={scene}>
    <header className="study-summer-subpage__header">
      <div><span className="study-summer-eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>
      <div className="study-summer-subpage__scene-picker" aria-label="场景切换">
        {STUDY_SCENES.map((item) => <button key={item.key} type="button" className={scene === item.key ? "is-active" : ""} aria-pressed={scene === item.key} onClick={() => onSelectScene(item.key)}>{item.label}<small>{item.caption}</small></button>)}
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
  const [searchParams] = useSearchParams();
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [title, setTitle] = useState("");
  const [saving, setSaving] = useState(false);
  // AI 拆解工作台（复用 POST /study/task-breakdown，仅后端保留模型密钥）
  const [planOpen, setPlanOpen] = useState(() => searchParams.get("ai") === "1");
  const [goal, setGoal] = useState("");
  const [breaking, setBreaking] = useState(false);
  const [breakdown, setBreakdown] = useState(null);
  const [steps, setSteps] = useState([]);
  const load = async () => { setLoading(true); setError(""); try { setTasks(itemsOf(await api.getTasks())); } catch (err) { logApiError("plans-load", err); setError(userErrorMessage(err, "学习清单加载失败")); } finally { setLoading(false); } };
  useEffect(() => { void load(); }, []);

  async function addTask(event) { event.preventDefault(); if (!title.trim() || saving) return; setSaving(true); try { const created = await api.createTask({ title: title.trim(), source_name: "学习陪伴清单" }); setTasks((current) => [created, ...current]); setTitle(""); } catch (err) { logApiError("plans-add", err); setError(userErrorMessage(err, "任务保存失败")); } finally { setSaving(false); } }
  async function toggleTask(task) { try { const updated = await api.completeTask(task.id, !isDone(task)); setTasks((current) => current.map((item) => item.id === task.id ? { ...item, ...updated, status: updated?.status || (!isDone(task) ? "completed" : "pending") } : item)); } catch (err) { logApiError("plans-toggle", err); setError(userErrorMessage(err, "任务状态更新失败")); } }
  async function removeTask(task) { if (!window.confirm(`删除“${task.title}”？`)) return; try { await api.deleteTask(task.id); setTasks((current) => current.filter((item) => item.id !== task.id)); } catch (err) { logApiError("plans-delete", err); setError(userErrorMessage(err, "任务删除失败")); } }

  const completed = tasks.filter(isDone).length;
  const pending = tasks.length - completed;

  async function generatePlan() {
    if (!goal.trim() || breaking) return;
    setBreaking(true); setError("");
    try {
      const result = await api.breakdownStudyTask({ goal: goal.trim() });
      setBreakdown(result);
      setSteps((result.steps || []).map((step, index) => ({
        _key: `${index}-${step.step_number || index + 1}`,
        title: step.title || "",
        description: step.description || "",
        estimated_minutes: Number(step.estimated_minutes) || 30,
      })));
    } catch (err) {
      logApiError("plans-breakdown", err);
      setError(userErrorMessage(err, "目标拆解失败，请重试"));
    } finally {
      setBreaking(false);
    }
  }
  function updateStep(index, patch) { setSteps((current) => current.map((item, i) => (i === index ? { ...item, ...patch } : item))); }
  function removeStep(index) { setSteps((current) => current.filter((_, i) => i !== index)); }
  async function confirmSaveSteps() {
    const valid = steps.filter((step) => step.title.trim());
    if (!valid.length) return;
    setSaving(true); setError("");
    try {
      const created = await Promise.all(valid.map((step) => api.createTask({
        title: step.title.trim(),
        description: step.description?.trim() || undefined,
        source_name: "AI 拆解步骤",
        source_text: breakdown?.goal || goal.trim(),
      })));
      setTasks((current) => [...created, ...current]);
      setBreakdown(null); setSteps([]); setGoal("");
      setNotice(`已将 ${created.length} 个步骤加入学习清单`);
    } catch (err) {
      logApiError("plans-save-steps", err);
      setError(userErrorMessage(err, "步骤保存失败，请重试"));
    } finally {
      setSaving(false);
    }
  }

  return <StudyShell eyebrow="Learning map" title="计划" description="把长期目标收拢成清晰、能执行的下一步。" scene={scene} onSelectScene={select} audio={audio}>
    <section className="study-sub-stats">
      <Stat label="学习任务" value={tasks.length} unit="项" icon="PhListChecks" />
      <Stat label="待完成" value={pending} unit="项" icon="PhHourglass" />
      <Stat label="已完成" value={completed} unit="项" icon="PhCheckCircle" />
      <Stat label="完成进度" value={tasks.length ? Math.round(completed / tasks.length * 100) : 0} unit="%" icon="PhChartLineUp" />
    </section>

    <section className="study-sub-panel study-plan-board">
      <div className="study-sub-panel__heading">
        <div><span className="study-sub-kicker">NEXT STEPS</span><h2>今天继续推进</h2><p>这里是与专注室同步的个人学习清单，每一条都是一个可独立勾选的待办。</p></div>
        <Link className="study-sub-link" to="/study">回到专注室 <Icon name="PhArrowUpRight" size={15} /></Link>
      </div>
      <form className="study-sub-create" onSubmit={addTask}><Icon name="PhPlus" size={18} /><input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="写下一个可以马上开始的步骤…" aria-label="新建学习任务" /><button type="submit" disabled={saving || !title.trim()}>{saving ? "保存中" : "加入清单"}</button></form>
      <p className="study-plan-note">目前每个待办作为独立个人任务保存；「计划 → 子任务 + 独立进度」的完整计划模型后端暂未提供，若需分组跟踪请等待契约升级。</p>
      {loading ? <LoadingState /> : error ? <LoadingState error={error} onRetry={load} /> : <div className="study-plan-list">{tasks.length ? tasks.map((task) => <article className={`study-plan-row${isDone(task) ? " is-done" : ""}`} key={task.id}><button className="study-plan-check" type="button" aria-label={isDone(task) ? "恢复任务" : "完成任务"} onClick={() => void toggleTask(task)}><Icon name={isDone(task) ? "PhCheckCircle" : "PhCircle"} size={20} weight={isDone(task) ? "fill" : "regular"} /></button><div><strong>{task.title || "未命名任务"}</strong><small>{task.deadline ? `截止 ${dateLabel(task.deadline)}` : task.source_name || "学习清单"}</small></div><button className="study-plan-delete" type="button" aria-label={`删除 ${task.title || "任务"}`} onClick={() => void removeTask(task)}><Icon name="PhTrash" size={16} /></button></article>) : <div className="study-sub-empty"><Icon name="PhFlag" size={30} /><p>清单还是空的，从一个明确的目标开始。</p></div>}</div>}
    </section>

    <section className="study-sub-panel study-plan-ai">
      <div className="study-sub-panel__heading">
        <div><span className="study-sub-kicker">AI PLANNER</span><h2>AI 目标拆解</h2><p>输入目标，由后端大模型生成可执行步骤；拆解前可预览、编辑或删除，确认后再加入清单。模型能力由服务端统一提供，密钥只保留在后端。</p></div>
        <button type="button" className={`study-sub-link-button${planOpen ? " is-open" : ""}`} onClick={() => setPlanOpen((value) => !value)}>{planOpen ? <><Icon name="PhArrowUp" size={14} /> 收起拆解台</> : <><Icon name="PhSparkle" size={14} /> 打开拆解台</>}</button>
      </div>
      {planOpen && <div className="study-ai-planner">
        <div className="study-ai-planner__input"><textarea value={goal} onChange={(event) => setGoal(event.target.value)} rows="2" placeholder="例如：复习高等数学第一章，并完成课后习题" aria-label="学习目标" /><Button icon="PhSparkle" disabled={breaking || !goal.trim()} onClick={generatePlan}>{breaking ? "正在拆解…" : breakdown ? "重新生成" : "生成步骤"}</Button></div>
        {breakdown?.mode === "rule_fallback" && <p className="study-ai-planner__note">当前为规则降级拆解（大模型服务暂不可用），步骤为通用模板，仍可按需编辑后使用。</p>}
        {breakdown?.warnings?.length > 0 && <ul className="study-ai-planner__warnings">{breakdown.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>}
        {steps.length > 0 && <div className="study-ai-steps">{steps.map((step, index) => <article key={step._key} className="study-ai-step">
          <div className="study-ai-step__num">{index + 1}</div>
          <div className="study-ai-step__fields">
            <input value={step.title} onChange={(event) => updateStep(index, { title: event.target.value })} aria-label={`第 ${index + 1} 步标题`} />
            <textarea value={step.description} onChange={(event) => updateStep(index, { description: event.target.value })} rows="2" aria-label={`第 ${index + 1} 步说明`} placeholder="这一步要怎么做…" />
            <label><span>预计</span><input type="number" min="5" max="120" value={step.estimated_minutes} onChange={(event) => updateStep(index, { estimated_minutes: Number(event.target.value) || 30 })} aria-label={`第 ${index + 1} 步预计分钟`} /><em>分钟</em></label>
          </div>
          <button type="button" className="study-ai-step__remove" onClick={() => removeStep(index)} aria-label={`删除第 ${index + 1} 步`}><Icon name="PhTrash" size={16} /></button>
        </article>)}</div>}
        {steps.length > 0 && <div className="study-ai-planner__save"><Button icon="PhListPlus" disabled={saving || !steps.some((step) => step.title.trim())} onClick={confirmSaveSteps}>{saving ? "保存中…" : "确认保存到清单"}</Button><span>{steps.length} 个步骤</span></div>}
        {notice && <p className="study-ai-planner__notice" role="status">{notice}</p>}
      </div>}
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
  const load = async () => { setLoading(true); setError(""); try { const [sessionList, checkinSummary, taskList] = await Promise.all([api.getStudySessions(), api.getStudyCheckins(), api.getTasks()]); setSessions(itemsOf(sessionList)); setCheckins(checkinSummary || { items: [] }); setTasks(itemsOf(taskList)); } catch (err) { logApiError("stats-load", err); setError(userErrorMessage(err, "学习统计加载失败")); } finally { setLoading(false); } };
  useEffect(() => { void load(); }, []);
  const completedSessions = useMemo(() => sessions.filter((item) => item.status === "completed"), [sessions]);
  const totalMinutes = completedSessions.reduce((total, item) => total + minutesOf(item), 0);
  const completedTasks = tasks.filter(isDone).length;
  const checkinCount = Number(checkins.total || checkins.items?.length || 0);
  const trend = useMemo(() => Array.from({ length: 7 }, (_, index) => { const date = new Date(); date.setHours(0, 0, 0, 0); date.setDate(date.getDate() - (6 - index)); const key = date.toISOString().slice(0, 10); const minutes = completedSessions.filter((item) => String(item.started_at || "").slice(0, 10) === key).reduce((sum, item) => sum + minutesOf(item), 0); return { label: new Intl.DateTimeFormat("zh-CN", { weekday: "short" }).format(date).replace("周", ""), minutes }; }), [completedSessions]);
  return <StudyShell eyebrow="Focus archive" title="统计" description="看见每一次出现、完成和继续。学习陪伴把专注记录整理成可回看的节奏。" scene={scene} onSelectScene={select} audio={audio}>
    {loading ? <LoadingState /> : error ? <LoadingState error={error} onRetry={load} /> : <><section className="study-sub-stats"><Stat label="累计专注" value={totalMinutes} unit="分钟" icon="PhClock" /><Stat label="完成会话" value={completedSessions.length} unit="次" icon="PhCheckCircle" /><Stat label="学习打卡" value={checkinCount} unit="天" icon="PhCalendar" /><Stat label="任务完成率" value={tasks.length ? Math.round(completedTasks / tasks.length * 100) : 0} unit="%" icon="PhChartLineUp" /></section><div className="study-stat-grid"><section className="study-sub-panel"><div className="study-sub-panel__heading"><div><span className="study-sub-kicker">LAST 7 DAYS</span><h2>专注趋势</h2><p>完成的学习会话按开始日期累计。</p></div><strong className="study-panel-number">{totalMinutes}<em> min</em></strong></div><div className="study-stat-chart" aria-label="近七日专注趋势">{trend.map((item) => <div key={item.label}><span style={{ height: `${Math.max(item.minutes ? 12 : 3, Math.round(item.minutes / Math.max(...trend.map((value) => value.minutes), 1) * 100))}%` }} /><small>{item.label}</small><b>{item.minutes || ""}</b></div>)}</div></section><section className="study-sub-panel"><div className="study-sub-panel__heading"><div><span className="study-sub-kicker">RECENT RECORDS</span><h2>最近记录</h2><p>每一次完成都会留下轨迹。</p></div><Link className="study-sub-link" to="/study">开始一次专注 <Icon name="PhArrowUpRight" size={15} /></Link></div><div className="study-record-list">{completedSessions.slice(0, 6).map((item) => <article key={item.id}><span><Icon name="PhCheckCircle" size={17} /></span><div><strong>{item.goal || "一次学习陪伴"}</strong><small>{dateLabel(item.started_at)} · {minutesOf(item)} 分钟</small></div></article>)}{!completedSessions.length && <div className="study-sub-empty study-sub-empty--inline"><Icon name="PhTimer" size={26} /><p>完成第一次专注后，这里会显示你的记录。</p></div>}</div></section></div></>}
  </StudyShell>;
}

export default function StudySubpages() {
  const { pathname } = useLocation();
  if (pathname.startsWith("/docs")) return <DocsPage />;
  if (pathname.startsWith("/statistics")) return <StatisticsPage />;
  return <PlansPage />;
}
