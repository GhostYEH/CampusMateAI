import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { Icon } from "../Icon.jsx";
import * as api from "../../data/api.js";
import { formatDateTime } from "../../utils/date.js";
import { describeEntryFailure, enterClassroomHref, resolveGenerationPhase, stageGenerationIdempotencyKey } from "../../features/magicclass/enterClassroomModel.js";
import { buildCourseRailItems, defaultMagicClassCourseId } from "../../features/magicclass/homeModel.js";
import { inferHomeGenerationMode } from "../../features/magicclass/homeGenerationModel.js";

const dateText = (value) => formatDateTime(value, { dateStyle: "medium", timeStyle: "short" }, "时间待定");

function CoursePicker({ courses, selectedCourseId, onSelectCourse }) {
  const [open, setOpen] = React.useState(false);
  const selected = courses.find((course) => String(course.id) === String(selectedCourseId));
  return <div className="magicclass-reference-picker">
    <button type="button" className="magicclass-reference-picker__trigger" aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen((value) => !value)}><Icon name="PhBookOpenText" size={16} aria-hidden="true" /><span>{selected?.name || selected?.title || "选择课程"}</span><Icon name={open ? "PhCaretUp" : "PhCaretDown"} size={14} aria-hidden="true" /></button>
    {open ? <div className="magicclass-reference-picker__menu" role="listbox" aria-label="选择课程">{courses.map((course) => <button type="button" role="option" aria-selected={String(course.id) === String(selectedCourseId)} key={course.id} onClick={() => { onSelectCourse(String(course.id)); setOpen(false); }}><span>{course.name || course.title || "未命名课程"}</span>{String(course.id) === String(selectedCourseId) ? <Icon name="PhCheck" size={14} aria-hidden="true" /> : null}</button>)}</div> : null}
  </div>;
}

function RecentClassrooms({ items, error }) {
  return <section className="magicclass-reference-recent" aria-labelledby="magicclass-recent-title"><div className="magicclass-reference-recent__rule" /><div className="magicclass-reference-recent__heading"><span id="magicclass-recent-title"><Icon name="PhClockCounterClockwise" size={15} />最近课堂</span><small>{items.length ? `${items.length} 个` : "暂无"}</small></div><div className="magicclass-reference-recent__rule" />{error ? <div className="magicclass-reference-empty" role="status"><Icon name="PhWarningCircle" size={18} /><span>{error}</span></div> : items.length ? <div className="magicclass-reference-recent__grid">{items.slice(0, 8).map((item) => <Link className="magicclass-reference-classroom" key={`${item.kind}:${item.id}`} to={item.href}><span className="magicclass-reference-classroom__cover"><Icon name="PhFileText" size={23} /></span><span className="magicclass-reference-classroom__copy"><strong>{item.courseName || item.title}</strong><small>{item.title} · {item.scenesCount ? `${item.scenesCount} 个场景` : "互动课堂"}</small><small>{dateText(item.updatedAt)}</small></span></Link>)}</div> : <div className="magicclass-reference-empty"><Icon name="PhClockCounterClockwise" size={21} /><span>还没有最近课堂<small>生成的课堂会在这里按最近更新时间出现。</small></span></div>}</section>;
}

function CourseLibrary({ courses, assignments }) {
  const items = buildCourseRailItems(courses, assignments);
  return <details className="magicclass-reference-library"><summary><span><Icon name="PhBooks" size={18} />我的课程</span><small>{items.length} 门课程</small><Icon name="PhCaretDown" size={15} /></summary><div className="magicclass-reference-library__list">{items.map((course) => <Link key={course.id} to={`/courses/${course.id}`}><span className="magicclass-reference-library__icon"><Icon name="PhBookOpenText" size={15} /></span><span><strong>{course.name}</strong><small>{[course.teacher, course.term, course.code].filter(Boolean).join(" · ")}</small></span><Icon name="PhArrowUpRight" size={14} /></Link>)}</div></details>;
}

export default function MagicClassHome({ courses = [], assignments = [], recentItems = [], fusion = null, providerStatus = null, recentError = "" }) {
  const navigate = useNavigate();
  const [selectedCourseId, setSelectedCourseId] = React.useState(() => defaultMagicClassCourseId(courses));
  const [prompt, setPrompt] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");
  const [phase, setPhase] = React.useState(null);
  const selectedCourse = courses.find((course) => String(course.id) === String(selectedCourseId));
  const canGenerate = Boolean(selectedCourseId && fusion?.state === "ready" && fusion?.capabilities?.includes("workspace") && fusion?.capabilities?.includes("generation") && providerStatus?.providers?.llm);
  React.useEffect(() => { if (!courses.some((course) => String(course.id) === String(selectedCourseId))) setSelectedCourseId(defaultMagicClassCourseId(courses)); }, [courses, selectedCourseId]);

  async function waitForJob(courseId, jobId, workspaceId) {
    for (let attempt = 0; attempt < 180; attempt += 1) {
      const job = await api.getMagicClassJob(courseId, jobId); setPhase(resolveGenerationPhase(job));
      if (job.status === "completed") { navigate(`/courses/${courseId}/workspaces/${workspaceId}?mode=playback`, { replace: true }); return; }
      if (["failed", "cancelled"].includes(job.status)) throw { response: { status: 200, data: job } };
      await new Promise((resolve) => window.setTimeout(resolve, 800));
    }
    throw new Error("课堂生成等待超时，请稍后从最近课堂恢复。");
  }

  async function submit(event) {
    event.preventDefault(); const topic = prompt.trim(); if (!topic || !selectedCourseId || busy) return;
    setBusy(true); setError(""); setPhase(null);
    try {
      const result = await api.generateMagicClassHome(selectedCourseId, { mode: inferHomeGenerationMode(topic), prompt: topic, idempotencyKey: stageGenerationIdempotencyKey(selectedCourseId, topic) });
      const workspaceId = result?.workspace_id;
      if (!workspaceId) throw new Error("网关未返回课程工作台");
      if (result?.job?.status === "completed") navigate(`/courses/${selectedCourseId}/workspaces/${workspaceId}?mode=playback`, { replace: true });
      else if (result?.job?.id) await waitForJob(selectedCourseId, result.job.id, workspaceId);
      else throw new Error("受管服务未返回生成任务");
    } catch (cause) { setError(describeEntryFailure(cause).message || cause?.message || "课堂生成失败，请重试。"); }
    finally { setBusy(false); }
  }

  const capabilityLabel = providerStatus?.providers?.llm ? "模型已连接" : "模型未配置";
  return <section className="magicclass-home magicclass-home--reference" aria-label="magic class 首页"><div className="magicclass-reference-glow magicclass-reference-glow--top" aria-hidden="true" /><div className="magicclass-reference-glow magicclass-reference-glow--bottom" aria-hidden="true" /><div className="magicclass-reference__brand"><span className="magicclass-reference__mark"><Icon name="PhCube" size={29} weight="duotone" /></span><span><strong>{"magic class"}</strong><small>Generative Learning in Multi-Agent Interactive Classroom</small></span></div>
    <form className="magicclass-reference-composer" onSubmit={submit}><div className="magicclass-reference-composer__top"><CoursePicker courses={courses} selectedCourseId={selectedCourseId} onSelectCourse={setSelectedCourseId} /><span className="magicclass-reference-composer__agents">嗨，同学 <Icon name="PhCaretDown" size={13} /></span></div><textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} maxLength={750} placeholder={'输入你想学习的任何内容，例如：\n「从零学习 Python，30 分钟写出第一个程序」\n「用矩阵乘法讲解傅里叶变换」\n「阿里跨库筛选怎么写」'} aria-label="学习主题" /><div className="magicclass-reference-composer__footer"><div className="magicclass-reference-tools" aria-label="课堂工具"><button type="button" aria-label="附件" disabled title="附件能力尚未接通"><Icon name="PhPaperclip" size={17} /></button><button type="button" aria-label="联网搜索" disabled title="联网搜索能力尚未接通"><Icon name="PhGlobe" size={17} /></button><button type="button" aria-label={capabilityLabel} className={providerStatus?.providers?.llm ? "is-ready" : ""} disabled title="模型选择由服务端课程配置管理"><Icon name="PhSlidersHorizontal" size={17} /></button></div><div className="magicclass-reference-actions"><button type="button" className="magicclass-reference-mode" disabled title="当前课程固定使用课堂生成模式">✦ 深度交互</button><button type="submit" aria-label="生成学习内容" className="magicclass-reference-submit" disabled={!canGenerate || !prompt.trim() || busy}>{busy ? (phase?.title || "生成中…") : "进入课堂"}<Icon name="PhArrowUp" size={15} /></button></div></div>{!canGenerate && !error ? <p className="magicclass-reference-hint" role="status">{providerStatus?.providers?.llm ? "课程生成能力正在准备，请稍后重试。" : "需要配置课程生成模型后才能创建真实课堂。"}</p> : null}{error ? <p className="magicclass-reference-error" role="alert">{error}</p> : null}</form>
    <div className="magicclass-classroom-entry">
      <span>已选课程：{selectedCourse?.name || selectedCourse?.title || "请选择课程"}</span>
      {selectedCourseId ? <Link className="button button-primary magicclass-classroom-entry__action" to={enterClassroomHref(selectedCourseId)} aria-label={`进入《${selectedCourse?.name || selectedCourse?.title || "当前课程"}》的课堂`}><Icon name="PhSparkle" size={17} />进入课堂</Link> : <button type="button" className="button button-primary magicclass-classroom-entry__action" disabled><Icon name="PhSparkle" size={17} />进入课堂</button>}
    </div>
    <p className="magicclass-classroom-entry__hint" role="status">直接进入会创建或恢复该课程的课堂；输入主题后则可生成新的学习内容。</p>
    <RecentClassrooms items={recentItems} error={recentError} /><CourseLibrary courses={courses} assignments={assignments} /><p className="magicclass-reference-footer">{"magic class Open Source Project"}</p>
  </section>;
}
