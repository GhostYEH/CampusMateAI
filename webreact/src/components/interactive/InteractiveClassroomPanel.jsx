import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../../data/api.js";
import { DEFAULT_TRUSTED_EMBED_HOSTS, INTERACTIVE_MODES, interactiveStepLabel, isTrustedEmbedUrl } from "../../data/interactiveClassroom.js";
import { Button, Panel, SectionHeading } from "../Primitives.jsx";
import { Icon } from "../Icon.jsx";

const errorText = (error, fallback = "操作失败，请稍后重试") => error?.response?.data?.detail || error?.response?.data?.message || (error?.response?.data?.code === "OPENMAIC_NOT_ENABLED" ? "互动课堂服务尚未配置，无法生成。" : null) || error?.message || fallback;

/**
 * 课程智能辅导空间面板。独立封装，自带状态与错误处理：
 * 服务不可用（enabled:false）或请求失败都只影响本面板，绝不抛到课程详情整页。
 * OpenMAIC 课堂 iframe / 新窗口链接仅在 host 落入可信白名单时才渲染（安全降级）。
 */
export default function InteractiveClassroomPanel({ courseId, trustedEmbedHosts = DEFAULT_TRUSTED_EMBED_HOSTS }) {
  const navigate = useNavigate();
  const [status, setStatus] = useState({ enabled: false, loading: true, unavailable: false });
  const [items, setItems] = useState([]);
  const [itemsLoading, setItemsLoading] = useState(false);
  const [mode, setMode] = useState("adaptive");
  const [learningObjective, setLearningObjective] = useState("");
  const [session, setSession] = useState(null);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showObjective, setShowObjective] = useState(false);
  const pollTimer = useRef(null);
  const alive = useRef(true);

  const loadOverview = async () => {
    setStatus((s) => ({ ...s, loading: true }));
    // status 接口已对失败宽容；此项失败也不应让其余 tabs 抛错。
    const result = await api.getInteractiveClassroomStatus(courseId);
    if (!alive.current) return;
    setStatus({ enabled: !!result.enabled, loading: false, unavailable: !!result.unavailable, service: result.service, version: result.version });
    if (result.enabled) {
      setItemsLoading(true);
      api.listInteractiveClassrooms(courseId).then((data) => { if (alive.current) setItems(data.items || []); }).catch(() => {}).finally(() => { if (alive.current) setItemsLoading(false); });
    } else {
      setItems([]);
    }
  };

  useEffect(() => {
    alive.current = true;
    loadOverview();
    return () => { alive.current = false; if (pollTimer.current) clearTimeout(pollTimer.current); };
  }, [courseId]);

  const stopPoll = () => { if (pollTimer.current) { clearTimeout(pollTimer.current); pollTimer.current = null; } };

  const schedulePoll = (sess) => {
    const delay = Number(sess.poll_interval_ms) || 3000;
    pollTimer.current = setTimeout(async () => {
      pollTimer.current = null;
      if (!alive.current) return;
      try {
        const job = await api.getInteractiveClassroomJob(courseId, sess.session_id || sess.id || sess.classroom_id);
        const next = job?.session || job;
        if (!alive.current) return;
        setSession(next);
        if (next.status === "done" || next.status === "succeeded") {
          setPolling(false);
          setNotice("课堂已生成");
        } else if (next.status === "failed") {
          setPolling(false);
          setError(errorText(next.message, "课堂生成失败，可重试。"));
        } else {
          schedulePoll(next);
        }
      } catch (err) {
        if (!alive.current) return;
        setPolling(false);
        setError(errorText(err, "进度查询失败"));
      }
    }, delay);
  };

  const startGenerate = async (targetMode = mode, retire = null) => {
    stopPoll();
    setError(""); setNotice(""); setSession(null); setPolling(true);
    const payload = { mode: targetMode, ...(learningObjective.trim() ? { learning_objective: learningObjective.trim() } : {}) };
    try {
      const resp = retire
        ? await api.retryInteractiveClassroom(courseId, retire.session_id || retire.id, payload)
        : await api.generateInteractiveClassroom(courseId, payload);
      const created = resp?.session || resp;
      if (!alive.current) return;
      setSession(created);
      schedulePoll(created);
    } catch (err) {
      if (!alive.current) return;
      setPolling(false);
      setError(errorText(err));
    }
  };

  const retryCurrent = () => {
    if (!session) { setError("暂无可重试的生成任务"); return; }
    startGenerate(mode, session);
  };

  const resetPanel = () => { stopPoll(); setError(""); setNotice(""); setSession(null); setPolling(false); setShowObjective(false); };

  const askCpm = () => {
    const prompt = mode ? `我想用「${INTERACTIVE_MODES.find((m) => m.mode === mode)?.label || mode}」方式学习这门课。` : "";
    const params = new URLSearchParams();
    params.set("course", courseId);
    if (prompt) params.set("prompt", prompt);
    navigate(`/counselor?${params.toString()}`);
  };

  const targetMode = INTERACTIVE_MODES.find((m) => m.mode === mode) || INTERACTIVE_MODES[0];
  const live = polling || (session && session.status && !["done", "succeeded", "failed"].includes(session.status));
  // 安全内嵌：host 必须落在可信白名单，否则不渲染 iframe（降级为新窗口）。
  const safeUrl = session?.url && isTrustedEmbedUrl(session.url, trustedEmbedHosts) ? session.url : null;
  const hasGeneratedUrl = Boolean(session?.url);
  const openInNewWindow = () => { if (safeUrl) window.open(safeUrl, "_blank", "noopener,noreferrer"); };
  const toggleFullscreen = () => {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
    else document.exitFullscreen?.();
  };

  if (status.loading) return <Panel className="interactive-panel"><SectionHeading title="智能辅导" detail="正在检测辅导服务…" /><div className="interactive-loading"><span className="loading-orb" /><p>正在检测互动课堂能力…</p></div></Panel>;

  if (!status.enabled) return <Panel className="interactive-panel"><SectionHeading title="智能辅导" detail="课程互动课堂" />
    <div className="interactive-unavailable interactive-state">
      <span className="interactive-state-icon"><Icon name={status.unavailable ? "PhWifiSlash" : "PhInfo"} size={26} /></span>
      <h3>{status.unavailable ? "辅导服务暂不可用" : "本课程尚未开启智能辅导"}</h3>
      <p>{status.unavailable ? "当前无法连接互动课堂服务，请稍后再试。这不影响课程其它内容。" : "OpenMAIC 互动课堂尚未为这门课配置。你可以先对 CPM 提问，获取学习建议。"}</p>
      <Button variant="quiet" icon="PhArrowClockwise" onClick={loadOverview}>重新检测</Button>
    </div></Panel>;

  return <Panel className="interactive-panel">
    <div className="interactive-panel-head"><SectionHeading title="智能辅导" detail={`互动课堂 · ${status.service || "OpenMAIC"}${status.version ? ` ${status.version}` : ""}`} action={<Button variant="quiet" icon="PhArrowsClockwise" disabled={polling} onClick={loadOverview}>刷新</Button>} /><button type="button" className="text-button interactive-ask-cpm" onClick={askCpm}><Icon name="PhChatCircleText" size={16} />问 CPM 了解这门课该如何学</button></div>

    {!live && !hasGeneratedUrl && <><div className="interactive-modes" role="radiogroup" aria-label="选择辅导模式">
      {INTERACTIVE_MODES.map((m) => <button key={m.mode} type="button" className={mode === m.mode ? "active" : ""} aria-pressed={mode === m.mode} onClick={() => { setMode(m.mode); setShowObjective(false); setError(""); }}><Icon name={m.mode === "adaptive" ? "PhPath" : m.mode === "explain" ? "PhChatCircleText" : m.mode === "explore" ? "PhMagnifyingGlass" : m.mode === "practice" ? "PhExam" : "PhTray"} size={20} /><strong>{m.label}</strong><small>{m.description}</small></button>)}
    </div>
    <div className="interactive-actions">
      <label className="interactive-objective"><span>{showObjective ? "学习目标" : "可选"}</span><input value={learningObjective} disabled={!showObjective} onChange={(e) => setLearningObjective(e.target.value)} placeholder={showObjective ? "例如：期中考试前巩固第 3 章难点" : ""} aria-label="补充学习目标" /></label>
      <Button variant="quiet" icon="PhPlus" onClick={() => setShowObjective((v) => !v)} disabled={polling}>{showObjective ? "收起学习目标" : "添加学习目标"}</Button>
    </div>
    <div className="interactive-actions interactive-primary">
      <Button icon="PhPlay" disabled={polling} onClick={() => startGenerate()}>开始生成 {targetMode.label}</Button>
      {error && <div className="interactive-error" role="alert"><Icon name="PhWarningCircle" size={16} />{error}<button type="button" className="text-button" onClick={retryCurrent}>重试</button></div>}
    </div>
    {itemsLoading ? <p className="interactive-hint">正在读取已生成的课堂…</p> : items.length > 0 && <div className="interactive-list"><h3>已生成的课堂</h3>{items.map((item) => <article className="interactive-item" key={item.session_id || item.id}><span className="row-icon tone-violet"><Icon name="PhGraduationCap" size={18} /></span><span className="row-copy"><strong>{INTERACTIVE_MODES.find((m) => m.mode === item.mode)?.label || item.mode || "互动课堂"}</strong><small>{item.scenes_count ? `${item.scenes_count} 个场景` : "互动课堂"} · {item.created_at ? new Date(item.created_at).toLocaleString("zh-CN") : "已生成"}</small></span>{item.url && isTrustedEmbedUrl(item.url, trustedEmbedHosts) ? <a className="button button-quiet" href={item.url} target="_blank" rel="noopener noreferrer">打开</a> : <Button variant="quiet" disabled>待打开</Button>}</article>)}</div>}
    </>}

    {live && <div className="interactive-progress" role="status" aria-live="polite">
      <div className="interactive-progress-head"><span>{interactiveStepLabel(session?.step)}</span><strong>{session?.progress != null ? `${session.progress}%` : "同步中"}</strong></div>
      <div className="mastery-track"><span style={{ width: `${Math.max(0, Math.min(100, Number(session?.progress) || 8))}%` }} /></div>
      <p>{session?.message || "正在生成你的互动课堂，请稍候…"}</p>
      <Button variant="quiet" icon="PhX" onClick={resetPanel}>取消</Button>
    </div>}

    {!live && session && session.status === "failed" && <div className="interactive-error interactive-state" role="alert"><Icon name="PhWarningCircle" size={20} /><p>{session.message || "课堂生成失败"}</p><Button onClick={retryCurrent}>重新生成</Button><Button variant="quiet" onClick={resetPanel}>放弃</Button></div>}

    {hasGeneratedUrl && !live && <div className="interactive-result">
      <div className="interactive-result-bar">
        {safeUrl ? <iframe className="interactive-frame" src={safeUrl} title="智能辅导互动课堂" aria-label="智能辅导互动课堂" sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-downloads" /> : <div className="interactive-fallback"><Icon name="PhLock" size={24} /><h3>无法在此内嵌课堂</h3><p>受浏览器安全策略限制，无法在此处安全内嵌该课堂页面。请在下方新窗口打开，或返回重新生成。</p></div>}
      </div>
      <div className="interactive-result-controls">
        {safeUrl ? <Button variant="quiet" icon="PhArrowsOut" onClick={toggleFullscreen}>全屏</Button> : null}
        <Button variant="quiet" icon="PhArrowSquareOut" onClick={openInNewWindow} aria-label="在新窗口打开课堂">新窗口打开课堂</Button>
        <Button variant="quiet" icon="PhArrowClockwise" onClick={resetPanel}>重新生成</Button>
        <Button variant="quiet" icon="PhBookOpen" onClick={loadOverview}>返回课堂列表</Button>
      </div>
    </div>}

    {notice && !live && <div className="page-notice notice-info" role="status">{notice}</div>}
  </Panel>;
}