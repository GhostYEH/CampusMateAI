import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import * as api from "../data/api.js";
import { itemsOf, normalizeNotice } from "../data/contracts.js";
import { noticeTaskDraft, updateNoticeTaskDraft } from "../data/alignment.js";
import { AsyncState, Button, LinkButton, PageFrame, Panel, SectionHeading } from "../components/Primitives.jsx";
import { Icon } from "../components/Icon.jsx";
import { formatDateTime } from "../utils/date.js";

const dateText = (value) => formatDateTime(value, { dateStyle: "medium", timeStyle: "short" }, "刚刚");
const errorText = (error, fallback) => error?.response?.data?.detail || error?.response?.data?.message || error?.message || fallback;

function Notice({ message, tone = "info" }) {
  return message ? <div className={`page-notice notice-${tone}`} role={tone === "error" ? "alert" : "status"}>{message}</div> : null;
}

function noticeSourceUrl(item) {
  if (item?.kind !== "unified" || !item.source_url) return null;
  try {
    const url = new URL(item.source_url, window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

export default function NoticeCenterPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("all");
  const [readFilter, setReadFilter] = useState("all");
  const [expanded, setExpanded] = useState(null);
  const [extractText, setExtractText] = useState("");
  const [extracting, setExtracting] = useState(false);
  const [extracted, setExtracted] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [notice, setNotice] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setItems(itemsOf(await api.getNotices()).map(normalizeNotice));
    } catch (cause) {
      setError(errorText(cause, "通知加载失败，请稍后重试"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);
  useEffect(() => {
    const initial = searchParams.get("extract");
    if (initial) setExtractText(initial);
  }, [searchParams]);

  const sources = useMemo(() => [...new Set(items.map((item) => item.source).filter(Boolean))], [items]);
  const unreadCount = useMemo(() => items.filter((item) => !item.has_read).length, [items]);
  const filtered = useMemo(() => items.filter((item) => (
    (source === "all" || item.source === source)
      && (readFilter === "all" || !item.has_read)
      && `${item.title || ""} ${item.content || ""}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())
  )), [items, query, readFilter, source]);

  async function toggle(item) {
    setExpanded((current) => current === item.id ? null : item.id);
    if (item.kind === "announcement" && !item.has_read) {
      try {
        await api.markAnnouncementRead(item.id);
        setItems((current) => current.map((value) => value.id === item.id ? { ...value, has_read: true } : value));
      } catch {
        setNotice("通知已打开，但已读状态同步失败");
      }
    }
  }

  function open(item) {
    const url = noticeSourceUrl(item);
    if (url) {
      window.open(url, "_blank", "noopener,noreferrer");
      return;
    }
    if (item.kind === "announcement") {
      navigate(`/announcements/${item.id}`);
      return;
    }
    setNotice("这条通知暂无可打开的原始链接");
  }

  async function extract() {
    if (!extractText.trim() || extracting) return;
    setExtracting(true);
    setSaved(false);
    setExtracted(null);
    try {
      setExtracted(await api.extractNotice(extractText.trim()));
    } catch (cause) {
      setExtracted({ error: errorText(cause, "提取失败，请检查通知内容") });
    } finally {
      setExtracting(false);
    }
  }

  function updateDraft(field, value) {
    setSaved(false);
    setExtracted((current) => updateNoticeTaskDraft(current, field, value));
  }

  async function saveTask() {
    const draft = noticeTaskDraft(extracted);
    const extractedTask = extracted?.tasks?.[0] || extracted || {};
    if (!draft.title.trim() || saving || saved) return;
    setSaving(true);
    try {
      await api.createTask({
        title: draft.title.trim(),
        description: extractedTask.source_text || extracted?.source_text || extractText,
        deadline: draft.deadline || null,
        materials: (extractedTask.materials || extracted?.materials || []).map((item) => item.name || item),
        submission_method: draft.submission_method || null,
        location: extractedTask.location || extracted?.location,
        source_name: extractedTask.source_name || extracted?.source_name || "校园通知",
        source_text: extractText,
        priority: ["high", "urgent"].includes(extractedTask.importance) ? "high" : "medium",
        importance: extractedTask.importance || "unknown"
      });
      setSaved(true);
      setNotice("已保存为个人待办");
    } catch (cause) {
      setNotice(errorText(cause, "保存待办失败"));
    } finally {
      setSaving(false);
    }
  }

  return <PageFrame className="notifications-page" showHeading={false}>
    <section className="notice-hero">
      <div className="notice-hero-copy">
        <span className="notice-hero-eyebrow">NOTICES / 校园信息</span>
        <h1>通知整理</h1>
        <p>先浏览课程通知，也可以粘贴一段原文，让系统提取截止时间并确认后保存为待办。</p>
      </div>
      <img src="/assets/campusmate-notice-illustration.png" alt="通知整理插画" />
      <div className="notice-hero-actions">
        <span className="notice-hero-sparkle" aria-hidden="true"><Icon name="PhSparkle" size={18} /></span>
        <LinkButton to="/profile/chaoxing" variant="secondary" icon="PhGraduationCap">管理学习通</LinkButton>
        <Button variant="secondary" icon="PhArrowClockwise" onClick={load}>刷新通知</Button>
      </div>
    </section>

    <div className="notice-layout">
      <Panel className="notice-list-column">
        <div className="notice-list-heading">
          <div>
            <span className="notice-list-kicker">{unreadCount} 条未读通知</span>
            <h2>通知列表</h2>
          </div>
          <div className="notice-count-tabs" role="tablist" aria-label="通知范围">
            <button type="button" role="tab" aria-selected={readFilter === "all"} className={readFilter === "all" ? "active" : ""} onClick={() => setReadFilter("all")}>全部 <b>{items.length}</b></button>
            <button type="button" role="tab" aria-selected={readFilter === "unread"} className={readFilter === "unread" ? "active" : ""} onClick={() => setReadFilter("unread")}>未读 <b>{unreadCount}</b></button>
          </div>
        </div>
        <div className="notice-toolbar filter-bar">
          <label className="search-field-wrap">
            <Icon name="PhMagnifyingGlass" size={17} />
            <input className="search-field" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索通知标题或内容" aria-label="搜索通知标题或内容" />
          </label>
          <select value={source} onChange={(event) => setSource(event.target.value)} aria-label="按来源筛选">
            <option value="all">全部课程班级</option>
            {sources.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </div>
        <AsyncState loading={loading} error={error} empty={!filtered.length ? "暂时没有匹配通知" : null} onRetry={load}>
          <div className="list-stack">
            {filtered.map((item) => <article className={`notice-row ${item.has_read ? "" : "unread"}`} key={`${item.kind}-${item.id}`}>
              <button className="list-row" onClick={() => toggle(item)} aria-expanded={expanded === item.id}>
                <span className="row-icon tone-violet"><Icon name={item.has_read ? "PhEnvelopeOpen" : "PhEnvelope"} size={18} /></span>
                <span className="row-copy"><strong>{item.title || "校园通知"}</strong><small>{item.source || "校园通知"} · {item.kind === "unified" ? "统一通知" : "课程公告"}</small></span>
                <span className="row-meta">{dateText(item.time || item.published_at || item.created_at)}</span>
                <Icon name={expanded === item.id ? "PhCaretDown" : "PhCaretRight"} size={16} />
              </button>
              {expanded === item.id && <div className="notice-expand-body"><p>{item.content || "暂无通知正文"}</p><div className="notice-expand-actions"><Button variant="quiet" icon="PhArrowUpRight" onClick={() => open(item)}>{item.kind === "unified" ? "打开原始通知" : "查看完整详情"}</Button><Button variant="quiet" icon="PhRobot" onClick={() => navigate(`/counselor?prompt=${encodeURIComponent(`请帮我处理这条通知：${item.title || "校园通知"}\n${item.content || ""}`)}`)}>交给 AI</Button></div></div>}
            </article>)}
          </div>
        </AsyncState>
      </Panel>

      <Panel className="notice-extract-panel">
        <div className="notice-step-heading"><span className="notice-step-number">1</span><SectionHeading title="从通知生成待办" detail="提取结果仅作为草稿，保存前请核对截止时间和提交方式。" /></div>
        <label className="notice-textarea-field">
          <span className="sr-only">通知原文</span>
          <textarea value={extractText} onChange={(event) => setExtractText(event.target.value)} rows="6" maxLength="20000" placeholder="粘贴教务处、学院或学生工作部门的通知原文" aria-label="通知原文" />
          <small>{extractText.length} / 5000</small>
        </label>
        <div className="form-footer notice-extract-actions">
          <Button className="extract-submit" disabled={extracting || !extractText.trim()} onClick={extract}>{extracting ? "正在提取…" : "开始提取"}<Icon name="PhArrowRight" size={17} /></Button>
          {extracted && !extracted.error && <Button variant="secondary" disabled={saving || saved} onClick={saveTask}>{saved ? "已保存到待办" : saving ? "保存中…" : "保存为待办"}</Button>}
        </div>
        {extracted?.error && <Notice message={extracted.error} tone="error" />}
        {extracted && !extracted.error && <div className="extract-result"><div className="notice-preview-heading"><span className="notice-step-number">2</span><h3>提取预览</h3></div><label className="field"><span>待办标题</span><input value={noticeTaskDraft(extracted).title} onChange={(event) => updateDraft("title", event.target.value)} /></label><label className="field"><span>截止时间</span><input type="text" value={noticeTaskDraft(extracted).deadline} onChange={(event) => updateDraft("deadline", event.target.value)} placeholder="未识别" /></label><label className="field"><span>提交方式</span><input value={noticeTaskDraft(extracted).submission_method} onChange={(event) => updateDraft("submission_method", event.target.value)} placeholder="未识别时可手动补充" /></label></div>}
      </Panel>
    </div>
    <Notice message={notice} />
  </PageFrame>;
}
