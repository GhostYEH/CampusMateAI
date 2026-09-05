import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import * as api from "../data/api.js";
import { itemsOf } from "../data/contracts.js";
import { isCompletedSubmissionStatus, isRenamedDuplicate, taskAssignmentProgress, taskAssignmentStatusLabel, taskGroupState, weeklyTrend } from "../data/alignment.js";
import { useApp } from "../app/AppContext.jsx";
import { AsyncState, Button, LinkButton, Modal, PageFrame, Panel, SectionHeading, StatCard } from "../components/Primitives.jsx";
import { Icon } from "../components/Icon.jsx";
import { formatDateTime, toDate } from "../utils/date.js";

const list = itemsOf;
const errorText = (error, fallback = "操作失败，请稍后重试") => error?.response?.data?.detail || error?.response?.data?.message || error?.message || fallback;
const dateText = (value) => formatDateTime(value, { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }, "未设置截止时间");
const localDateTime = (value) => {
  if (!value) return "";
  const date = toDate(value);
  if (!date) return "";
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
};
const blankTask = () => ({ title: "", deadline: "", priority: "medium", description: "", reminder_minutes: 30 });
const taskGroupMeta = { today: ["今天", "PhSun"], upcoming: ["未来 7 天", "PhCalendarBlank"], later: ["更晚", "PhCalendarPlus"], completed: ["已完成", "PhCheckCircle"] };

const taskKey = (task) => `${task.kind}-${task.sourceId || task.id}`;

function TaskRow({ task, onToggle, onEdit, onDelete, onPostpone, onOpen, onDragStart, onDragOver, onDrop }) {
  const state = taskGroupState(task);
  const progress = Math.max(0, Math.min(100, Number(task.progress ?? (task.done ? 100 : 0))));
  const statusLabel = task.kind === "assignment" && task.statusLabel ? task.statusLabel : task.done ? "已完成" : ({ overdue: "已逾期", today: "今日待办", upcoming: "即将截止" }[state] || "待完成");
  return <article className={`task-row panel task-state-${state}`} draggable onDragStart={() => onDragStart?.(task)} onDragOver={(event) => { event.preventDefault(); onDragOver?.(task); }} onDrop={() => onDrop?.(task)}>
    <span className="task-drag-handle" aria-hidden="true" title="拖动排序"><Icon name="PhDotsSixVertical" size={17} /></span>
    <button className="task-row-main" onClick={() => (onOpen ? onOpen(task) : onToggle?.(task))}>
      <span className={`task-check ${task.done ? "done" : ""}`} aria-hidden="true"><Icon name={task.done ? "PhCheckCircle" : "PhCircle"} size={21} /></span>
      <span className="task-row-copy"><strong>{task.title || "未命名任务"}</strong><small>{task.typeLabel} · {task.source}</small><span className="task-progress" aria-label={`进度 ${progress}%`}><i style={{ width: `${progress}%` }} /></span></span>
    </button>
    <span className="task-row-deadline"><small>{task.done ? "已完成" : state === "overdue" ? "已逾期" : "截止"}</small><time>{dateText(task.deadline)}</time></span>
    <span className={`task-priority priority-${task.priority}`}><i />{({ high: "高", medium: "中", low: "低" })[task.priority] || "中"}</span>
    <span className={`task-importance importance-${task.importance || "unknown"}`}><i />{({ urgent: "紧急", high: "重要", important: "重要", medium: "一般", normal: "一般", low: "较低", unknown: "待定" })[task.importance] || "待定"}</span>
    <span className={`task-status task-status-${state}`}>{statusLabel}</span>
    <div className="task-row-actions">
      {(task.kind === "personal" || task.kind === "local") && <>
        <Button variant="quiet" onClick={() => onToggle(task)}>{task.done ? "恢复" : "完成"}</Button>
        <Button variant="quiet" onClick={() => onEdit(task)}>编辑</Button>
        <Button variant="quiet" onClick={() => onPostpone(task)}>延期</Button>
        <Button variant="danger" onClick={() => onDelete(task)}>删除</Button>
      </>}
      {task.kind === "assignment" && <Link className="text-button" to={`/tasks/assignment/${task.sourceId}`}>查看作业</Link>}
    </div>
  </article>;
}

function TaskEditor({ task, saving, onClose, onSave }) {
  const [form, setForm] = useState(() => task ? { ...blankTask(), ...task, deadline: localDateTime(task.deadline) } : blankTask());
  const set = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  return <Modal title={task ? "编辑待办" : "新建待办"} onClose={onClose} actions={<><Button variant="secondary" type="button" onClick={onClose}>取消</Button><Button disabled={saving || !form.title.trim()} onClick={() => onSave({ ...form, title: form.title.trim(), deadline: form.deadline ? new Date(form.deadline).toISOString() : null })}>{saving ? "保存中…" : "保存待办"}</Button></>}>
    <div className="stack">
      <div className="field"><label htmlFor="task-editor-title">事项名称</label><input id="task-editor-title" name="title" value={form.title} maxLength={256} onChange={(event) => set("title", event.target.value)} placeholder="例如：准备奖学金申请材料" /></div>
      <div className="form-grid"><div className="field"><label htmlFor="task-editor-deadline">截止时间</label><input id="task-editor-deadline" name="deadline" type="datetime-local" value={form.deadline} onChange={(event) => set("deadline", event.target.value)} /></div><div className="field"><label htmlFor="task-editor-priority">优先级</label><select id="task-editor-priority" name="priority" value={form.priority} onChange={(event) => set("priority", event.target.value)}><option value="high">高优先级</option><option value="medium">中优先级</option><option value="low">低优先级</option></select></div></div>
      <div className="field"><label htmlFor="task-editor-reminder">提醒</label><select id="task-editor-reminder" name="reminder_minutes" value={form.reminder_minutes} onChange={(event) => set("reminder_minutes", Number(event.target.value))}><option value="0">截止时提醒</option><option value="30">提前 30 分钟</option><option value="1440">提前 1 天</option></select></div>
      <div className="field"><label htmlFor="task-editor-description">备注 <span className="muted-copy">选填</span></label><textarea id="task-editor-description" name="description" rows="4" maxLength={4000} value={form.description} onChange={(event) => set("description", event.target.value)} placeholder="补充材料、地点或下一步…" /></div>
    </div>
  </Modal>;
}

function ImportEditor({ saving, onClose, onAnalyze, onCommit }) {
  const [sourceName, setSourceName] = useState("学习材料");
  const [content, setContent] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function analyze() { if (!content.trim() || busy) return; setBusy(true); setError(""); try { const analyzed = await onAnalyze({ content: content.trim(), source_name: sourceName.trim() || null }); setResult({ ...analyzed, tasks: (analyzed.tasks || []).map((item) => ({ ...item, original_title: item.title })) }); } catch (err) { setError(errorText(err, "材料分析失败，请检查内容后重试")); } finally { setBusy(false); } }
  function reset() { setResult(null); setError(""); }
  async function commit() { const selected = (result?.tasks || []).filter((item) => item.selected !== false && !isRenamedDuplicate(item)); if (!selected.length) return; setBusy(true); setError(""); try { await onCommit(selected); onClose(); } catch (err) { setError(errorText(err, "保存导入任务失败")); } finally { setBusy(false); } }
  const importable = (result?.tasks || []).filter((item) => item.selected !== false && !isRenamedDuplicate(item));
  return <Modal title={result ? "确认识别结果" : "导入学习材料"} onClose={() => !busy && onClose()} actions={result ? <><Button variant="secondary" type="button" onClick={reset}>返回修改原文</Button><Button disabled={busy || saving || !importable.length} onClick={commit}>{busy || saving ? "保存中…" : `保存 ${importable.length} 项任务`}</Button></> : <><Button variant="secondary" type="button" onClick={onClose}>取消</Button><Button disabled={busy || !content.trim()} onClick={analyze}>{busy ? "正在分析…" : "分析并拆分"}</Button></>}>
    {!result ? <div className="stack"><div className="import-hero"><img src="/assets/campusmate-hero-illustration.png" alt="" /><div><strong>把一段材料变成清晰行动项</strong><small>AI 只会分析你粘贴的内容，保存前仍由你确认。</small></div></div><div className="field"><label htmlFor="import-source">材料名称</label><input id="import-source" name="source_name" value={sourceName} onChange={(event) => setSourceName(event.target.value)} maxLength={256} /></div><div className="field"><label htmlFor="import-content">计划内容</label><textarea id="import-content" name="content" value={content} onChange={(event) => setContent(event.target.value)} rows="10" maxLength={20000} placeholder="粘贴课程通知、复习计划或清单…" /></div><p className="muted-copy"><Icon name="PhShieldCheck" size={15} /> 只保存你确认的任务，不会覆盖已有进度。</p></div> : <div className="stack"><p className="muted-copy"><Icon name="PhListChecks" size={15} /> 识别到 {(result.tasks || []).length} 项，最多保留 50 项。</p>{(result.tasks || []).length ? <div className="stack">{result.tasks.map((draft, index) => { const duplicate = isRenamedDuplicate(draft); return <article className={`import-task panel ${draft.existing_task_id ? "is-duplicate" : ""}`} key={`${draft.title}-${index}`}><label className="check-label"><input type="checkbox" checked={draft.selected !== false} disabled={duplicate} onChange={(event) => setResult((current) => ({ ...current, tasks: current.tasks.map((item, itemIndex) => itemIndex === index ? { ...item, selected: event.target.checked } : item) }))} />保留</label><input aria-label="任务标题" value={draft.title || ""} onChange={(event) => setResult((current) => ({ ...current, tasks: current.tasks.map((item, itemIndex) => itemIndex === index ? { ...item, title: event.target.value } : item) }))} /><textarea aria-label="任务备注" rows="2" value={draft.description || ""} onChange={(event) => setResult((current) => ({ ...current, tasks: current.tasks.map((item, itemIndex) => itemIndex === index ? { ...item, description: event.target.value } : item) }))} /><select aria-label="优先级" value={draft.priority || "medium"} onChange={(event) => setResult((current) => ({ ...current, tasks: current.tasks.map((item, itemIndex) => itemIndex === index ? { ...item, priority: event.target.value } : item) }))}><option value="high">高</option><option value="medium">中</option><option value="low">低</option></select>{draft.existing_task_id && <small className="muted-copy">{duplicate ? "已有同名任务，修改标题后可重新导入" : "标题已修改，将作为新任务导入"}</small>}</article>; })}</div> : <div className="inline-empty">没有识别到明确任务，请使用项目符号或编号列出每一项。</div>}</div>}
    {error && <p className="page-notice notice-error" role="alert">{error}</p>}
  </Modal>;
}

export default function TasksPage() {
  const navigate = useNavigate();
  const { tasks: localTasks, toggleTask, updateTask: updateLocalTask, deleteTask: deleteLocalTask } = useApp();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");
  const [status, setStatus] = useState("all");
  const [sort, setSort] = useState("deadline");
  const [manualOrder, setManualOrder] = useState([]);
  const [collapsedGroups, setCollapsedGroups] = useState({ today: false, upcoming: false, later: false, completed: true });
  const [dragging, setDragging] = useState(null);
  const [editor, setEditor] = useState(null);
  const [importOpen, setImportOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  async function load() { setLoading(true); setError(""); try { setData(await Promise.all([api.getAssignments(), api.getTasks()])); } catch (err) { setError(errorText(err, "待办数据加载失败")); } finally { setLoading(false); } }
  useEffect(() => { load(); }, []);
  const tasks = useMemo(() => {
    const [assignments, personal] = data || [[], []];
    return [...list(assignments).map((item) => ({ ...item, kind: "assignment", typeLabel: "课程作业", sourceId: item.id, source: item.course_name || item.class_name || "课程作业", done: isCompletedSubmissionStatus(item.submission_status), progress: item.progress ?? taskAssignmentProgress(item.submission_status), statusLabel: taskAssignmentStatusLabel(item.submission_status), priority: item.priority || "medium", importance: item.importance || "unknown" })), ...list(personal).map((item) => ({ ...item, kind: "personal", typeLabel: "个人待办", sourceId: item.id, source: item.source_name || "个人安排", done: item.status === "completed", progress: item.progress ?? (item.status === "completed" ? 100 : 0), statusLabel: item.status === "completed" ? "已完成" : "待完成", priority: item.priority || "medium", importance: item.importance || "unknown" })), ...localTasks.map((item) => ({ ...item, kind: "local", typeLabel: "本地待办", sourceId: item.id, source: "当前浏览器", deadline: item.deadline || (item.due && item.due !== "待设置" ? item.due : null), description: item.description || item.details || "", done: Boolean(item.done), progress: item.progress ?? (item.done ? 100 : 0), statusLabel: item.done ? "已完成" : "待完成", priority: item.priority || "medium", importance: item.importance || "unknown" }))];
  }, [data, localTasks]);
  const visible = useMemo(() => tasks.filter((task) => {
    const haystack = `${task.title || ""} ${task.source || ""} ${task.course_name || ""}`.toLocaleLowerCase();
    const state = taskGroupState(task);
    const matchesStatus = status === "all" ? true : status === "done" ? task.done : status === "pending" ? !task.done : state === status;
    return (!query.trim() || haystack.includes(query.trim().toLocaleLowerCase())) && (kind === "all" || task.kind === kind) && matchesStatus;
  }).sort((left, right) => {
    if (sort === "title") return (left.title || "").localeCompare(right.title || "", "zh-CN");
    if (sort === "latest") return new Date(right.created_at || right.updated_at || 0) - new Date(left.created_at || left.updated_at || 0);
    if (sort === "custom") return (manualOrder.indexOf(taskKey(left)) < 0 ? Number.MAX_SAFE_INTEGER : manualOrder.indexOf(taskKey(left))) - (manualOrder.indexOf(taskKey(right)) < 0 ? Number.MAX_SAFE_INTEGER : manualOrder.indexOf(taskKey(right)));
    return new Date(left.deadline || "2999-01-01") - new Date(right.deadline || "2999-01-01");
  }), [tasks, query, kind, status, sort, manualOrder]);
  const groups = useMemo(() => {
    const next = { today: [], upcoming: [], later: [], completed: [] };
    visible.forEach((task) => {
      const state = taskGroupState(task);
      if (state === "completed") next.completed.push(task);
      else if (state === "overdue" || state === "today") next.today.push(task);
      else if (state === "upcoming") next.upcoming.push(task);
      else next.later.push(task);
    });
    return next;
  }, [visible]);
  const metrics = { total: tasks.length, pending: tasks.filter((item) => !item.done).length, completed: tasks.filter((item) => item.done).length, today: tasks.filter((item) => taskGroupState(item) === "today").length, upcoming: tasks.filter((item) => taskGroupState(item) === "upcoming").length, overdue: tasks.filter((item) => taskGroupState(item) === "overdue").length };
  const completionTrend = useMemo(() => weeklyTrend(tasks.filter((item) => item.done), new Date(), "completed_at"), [tasks]);
  async function toggle(task) { setSaving(true); try { await api.completeTask(task.sourceId, !task.done); setNotice(task.done ? "已恢复待办" : "任务已完成"); await load(); } catch (err) { setNotice(errorText(err)); } finally { setSaving(false); } }
  async function saveTask(form) { setSaving(true); try { if (editor?.kind === "local") { updateLocalTask(editor.sourceId, { ...form, due: form.deadline || "待设置" }); setNotice("本地待办已更新"); } else if (editor?.id) { await api.updateTask(editor.id, form); setNotice("待办已更新"); } else { await api.createTask({ ...form, source_name: "个人安排" }); setNotice("待办已加入清单"); } setEditor(null); if (editor?.kind !== "local") await load(); } catch (err) { setNotice(errorText(err)); } finally { setSaving(false); } }
  async function remove(task) { if (!window.confirm("确认删除这条个人待办吗？")) return; try { if (task.kind === "local") { deleteLocalTask(task.sourceId); } else { await api.deleteTask(task.sourceId); await load(); } setNotice("待办已删除"); } catch (err) { setNotice(errorText(err)); } }
  async function postpone(task) { const date = task.deadline ? new Date(task.deadline) : new Date(); date.setDate(date.getDate() + 1); try { if (task.kind === "local") { updateLocalTask(task.sourceId, { deadline: date.toISOString(), due: date.toISOString() }); } else { await api.updateTask(task.sourceId, { deadline: date.toISOString() }); await load(); } setNotice("已延期一天"); } catch (err) { setNotice(errorText(err)); } }
  async function commitImport(drafts) {
    await api.commitTaskImport({ tasks: drafts.map((draft) => {
      const task = { title: draft.title.trim() };
      ["description", "deadline", "materials", "submission_method", "location", "source_name", "source_text", "priority", "importance", "reminder_minutes"].forEach((field) => {
        if (draft[field] !== undefined && draft[field] !== null && draft[field] !== "") task[field] = draft[field];
      });
      if (!task.source_name) task.source_name = "学习材料";
      return task;
    }) });
    setNotice("导入任务已保存");
    await load();
  }
  function reorderTask(target) {
    if (!dragging || taskKey(dragging) === taskKey(target)) return;
    const order = manualOrder.length ? [...manualOrder] : tasks.map(taskKey);
    const from = order.indexOf(taskKey(dragging)); const to = order.indexOf(taskKey(target));
    if (from < 0 || to < 0) return;
    const [moved] = order.splice(from, 1); order.splice(to, 0, moved);
    setManualOrder(order); setSort("custom"); setDragging(null); setNotice("任务顺序已更新");
  }
  return <PageFrame eyebrow="Work / Tasks" title="待办与作业" description="把课程作业和个人安排放在一起，专注今天真正重要的事情。" actions={<><Button variant="secondary" icon="PhUpload" onClick={() => setImportOpen(true)}>导入材料</Button><Button icon="PhPlus" onClick={() => setEditor({})}>新建待办</Button></>}>
    {notice && <div className="page-notice notice-info" role="status">{notice}</div>}
    <AsyncState loading={loading} error={error} onRetry={load}>
      <div className="stack reveal"><div className="stat-grid"><StatCard label="今日待办" value={metrics.today} detail={metrics.overdue ? `${metrics.overdue} 项已逾期` : "今天安排"} icon="PhClipboardText" tone="violet" /><StatCard label="即将截止" value={metrics.upcoming} detail="未来 7 天" icon="PhCalendarBlank" tone="orange" /><StatCard label="已完成" value={metrics.completed} detail={`${metrics.total ? Math.round(metrics.completed / metrics.total * 100) : 0}% 完成率`} icon="PhCheckCircle" tone="green" /><StatCard label="待处理" value={metrics.pending} detail="继续推进" icon="PhTimer" tone="blue" /></div><Panel className="task-trend-panel"><SectionHeading title="近七日完成趋势" detail={`${metrics.completed} 项任务已完成`} /><div className="trend-bars" aria-label="近七日完成趋势">{completionTrend.map((item) => <span key={item.date}><i style={{ height: `${Math.max(item.count ? 14 : 4, Math.round(item.count / Math.max(...completionTrend.map((value) => value.count), 1) * 100))}%` }} /><small>{item.label}</small><b>{item.count || ""}</b></span>)}</div></Panel>
        <Panel className="task-focus-panel"><SectionHeading title="优先处理" detail="先从逾期和今天到期的事项开始" />{tasks.filter((task) => ["overdue", "today"].includes(taskGroupState(task)) && !task.done).slice(0, 3).map((task) => <button className="focus-task" key={`${task.kind}-${task.sourceId}`} onClick={() => task.kind === "assignment" ? navigate(`/tasks/assignment/${task.sourceId}`) : setEditor(task)}><Icon name={taskGroupState(task) === "overdue" ? "PhWarningCircle" : "PhFlag"} size={18} /><span><strong>{task.title || "未命名任务"}</strong><small>{taskGroupState(task) === "overdue" ? "已逾期" : "今天截止"} · {dateText(task.deadline)}</small></span><Icon name="PhArrowUpRight" size={16} /></button>)}{!tasks.some((task) => ["overdue", "today"].includes(taskGroupState(task)) && !task.done) && <div className="inline-empty">当前没有紧迫事项，适合安排一次专注。</div>}</Panel>
        <div className="filter-bar task-toolbar"><label className="search-field-wrap"><Icon name="PhMagnifyingGlass" size={17} /><input className="search-field" name="task-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索任务标题或课程…" /></label><select aria-label="任务类型" value={kind} onChange={(event) => setKind(event.target.value)}><option value="all">全部类型</option><option value="personal">个人待办</option><option value="assignment">课程作业</option><option value="local">本地待办</option></select><select aria-label="任务状态" value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">全部状态</option><option value="pending">未完成</option><option value="today">今日</option><option value="upcoming">即将截止</option><option value="overdue">已逾期</option><option value="done">已完成</option></select><select aria-label="任务排序" value={sort} onChange={(event) => setSort(event.target.value)}><option value="deadline">截止时间</option><option value="latest">最近创建</option><option value="title">标题</option><option value="custom">自定义顺序</option></select><LinkButton to="/study" variant="quiet" icon="PhTimer">开始专注</LinkButton></div>
        {visible.length ? <div className="task-list task-list-grouped">{Object.entries(groups).map(([group, groupTasks]) => <section className="task-group" key={group}><header className="task-group-head"><button type="button" className="task-group-toggle" aria-expanded={!collapsedGroups[group]} onClick={() => setCollapsedGroups((current) => ({ ...current, [group]: !current[group] }))}><Icon name={collapsedGroups[group] ? "PhCaretRight" : "PhCaretDown"} size={14} /><Icon name={taskGroupMeta[group][1]} size={15} /><strong>{taskGroupMeta[group][0]}</strong><b>{groupTasks.length}</b></button>{group === "today" && <span className="task-group-hint">逾期事项优先显示</span>}</header>{!collapsedGroups[group] && <div className="task-group-items">{groupTasks.map((task) => <TaskRow key={taskKey(task)} task={task} onToggle={task.kind === "local" ? (item) => toggleTask(item.sourceId) : toggle} onEdit={(item) => item.kind === "personal" || item.kind === "local" ? setEditor(item) : navigate(`/tasks/${item.kind}/${item.sourceId}`)} onDelete={remove} onPostpone={postpone} onOpen={task.kind === "local" ? undefined : (item) => navigate(`/tasks/${item.kind}/${item.sourceId}`)} onDragStart={setDragging} onDrop={reorderTask} />)}</div>}</section>)}</div> : <div className="state-card empty-state"><Icon name="PhStack" size={34} /><p>还没有匹配的任务</p><Button onClick={() => setEditor({})}>新建待办</Button></div>}
      </div>
    </AsyncState>
    {editor && <TaskEditor task={editor.id ? editor : null} saving={saving} onClose={() => setEditor(null)} onSave={saveTask} />}
    {importOpen && <ImportEditor saving={saving} onClose={() => setImportOpen(false)} onAnalyze={api.analyzeTaskImport} onCommit={commitImport} />}
  </PageFrame>;
}
