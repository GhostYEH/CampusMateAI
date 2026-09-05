import { useEffect, useMemo, useState } from "react";
import { BackLink, Button, Modal, PageFrame, Panel, SectionHeading } from "../components/Primitives.jsx";
import { Icon } from "../components/Icon.jsx";
import * as api from "../data/api.js";
import { chaoxingSyncSummary, isChaoxingConnected } from "../data/alignment.js";
import { formatDateTime } from "../utils/date.js";

const asItems = (value) => Array.isArray(value) ? value : value?.items || [];
const errorText = (error, fallback = "操作失败，请稍后重试") => error?.response?.data?.message || error?.response?.data?.detail || error?.message || fallback;
const formatDate = (value) => formatDateTime(value, { dateStyle: "medium", timeStyle: "short" }, "暂无记录");

function Notice({ message, tone = "info" }) {
  return message ? <div className={`page-notice notice-${tone}`} role={tone === "error" ? "alert" : "status"}><Icon name={tone === "error" || tone === "warning" ? "PhWarningCircle" : "PhInfo"} size={17} />{message}</div> : null;
}

const connectionLabels = { idle: "未连接", connecting: "连接中…", auth_required: "需要登录验证", waiting_user_login: "等待用户登录", need_captcha: "需要图片验证码", need_slider: "需要滑块验证", need_sms: "需要短信验证码", need_mfa: "需要多因素认证", authenticated: "已认证", syncing: "同步中…", connected: "已连接", session_expired: "登录已过期", auth_failed: "认证失败", network_error: "网络错误", system_unavailable: "教务系统暂不可用", unsupported: "暂未适配", error: "连接出错" };
const connectionLabel = (state, code) => code === "NEED_CAPTCHA" ? "学校要求完成图片验证码" : connectionLabels[state] || state || "未知状态";

function EduStatus({ status, binding, connection }) {
  const state = connection?.state || binding?.connection_status || status?.status || "unbound";
  return <Panel className="integration-hero"><div><span className="eyebrow">ACADEMIC CONNECTION</span><h2>{state === "active" || state === "connected" ? "教务系统已连接" : connectionLabel(state, connection?.error_code)}</h2><p>{binding?.provider || status?.provider || "选择学校后即可开始配置教务同步"}{binding?.external_student_id ? ` · 学号 ${binding.external_student_id}` : ""}</p></div><span className={`status-badge ${state === "active" || state === "connected" ? "success" : ""}`}>{connectionLabel(state, connection?.error_code)}</span></Panel>;
}

function SchedulePanel({ items, onOpen, action }) {
  const grouped = useMemo(() => asItems(items).filter((item) => !item.is_stale).reduce((map, item) => { const day = Number(item.weekday) || 0; (map[day] ||= []).push(item); return map; }, {}), [items]);
  return <Panel><SectionHeading title="本学期课表" detail="点击课程查看教师、地点和周次" action={action} />{Object.keys(grouped).length ? <div className="schedule-week-grid">{Object.entries(grouped).sort(([a], [b]) => Number(a) - Number(b)).map(([day, dayItems]) => <div key={day}><h3>{["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"][day] || "其他"}</h3><div className="schedule-card-list">{dayItems.sort((a, b) => (a.start_section || 99) - (b.start_section || 99)).map((item) => <button className="schedule-course-card" key={item.id || `${day}-${item.course_name}-${item.start_section}`} onClick={() => onOpen(item)}><strong>{item.course_name || item.name || "未命名课程"}</strong><small>{item.location || "地点待定"}</small><span>{item.start_section ? `第${item.start_section}${item.end_section && item.end_section !== item.start_section ? `-${item.end_section}` : ""}节` : item.start_time || "时间待定"}</span></button>)}</div></div>)}</div> : <div className="inline-empty"><Icon name="PhCalendarBlank" size={26} />暂无课表数据，请先同步课表</div>}</Panel>;
}

export function AcademicPage() {
  const [state, setState] = useState({ loading: true, error: "", status: {}, binding: null, records: [] });
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [manualUrl, setManualUrl] = useState("");
  const [probe, setProbe] = useState(null);
  const [connection, setConnection] = useState(null);
  const [connectionError, setConnectionError] = useState("");
  const [credentials, setCredentials] = useState({ username: "", password: "" });
  const [captcha, setCaptcha] = useState("");
  const [preLogin, setPreLogin] = useState(null);
  const [universityQuery, setUniversityQuery] = useState("");
  const [universities, setUniversities] = useState([]);
  const [schedule, setSchedule] = useState([]);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [selectedCourse, setSelectedCourse] = useState(null);

  async function load() {
    setState((current) => ({ ...current, loading: true, error: "" }));
    const [status, binding, records] = await Promise.all([
      api.getAcademicStatus().catch(() => ({ status: "unsupported", provider: "unsupported" })),
      api.getEduBinding().catch(() => null), api.getEduSyncRecords(10).catch(() => []),
    ]);
    setState({ loading: false, error: "", status, binding, records: asItems(records) });
  }
  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (!connection?.id || connection.state === "connected") return undefined;
    const timer = window.setInterval(async () => { try { const next = await api.pollEduConnection(connection.id); setConnection(next); if (next.state === "connected") load(); } catch { /* transient polling failures are expected */ } }, 3000);
    return () => window.clearInterval(timer);
  }, [connection?.id, connection?.state]);

  async function searchUniversities() { try { setUniversities(asItems(await api.getUniversities({ q: universityQuery, page_size: 20 }))); } catch { setUniversities([]); } }
  async function pickUniversity(id) { try { await api.selectUniversity(id); await load(); } catch (error) { setState((current) => ({ ...current, error: errorText(error, "选择大学失败") })); } }
  async function sync(type) { setBusy(type); setNotice(""); try { await api.syncEdu(type); setNotice(`${type === "profile" ? "基本信息" : type === "schedule" ? "课表" : type === "grade" ? "成绩" : "考试"}同步已提交`); await load(); } catch (error) { setNotice(errorText(error, "同步失败")); } finally { setBusy(""); } }
  async function probeAndConnect(event) { event.preventDefault(); setConnectionError(""); setProbe(null); setConnection(null); setBusy("probe"); try { const result = await api.probeEduPortal(manualUrl.trim()); setProbe(result); const next = await api.createEduConnection(manualUrl.trim(), state.status?.university_id); setConnection(next); } catch (error) { setConnectionError(errorText(error, "探测或创建连接失败")); } finally { setBusy(""); } }
  async function submitCredentials(event) { event.preventDefault(); if (!connection?.id) return; setBusy("credentials"); setConnectionError(""); try { const next = await api.continueEduConnection(connection.id, { username: credentials.username, password: credentials.password }); setConnection(next); if (next.state === "connected") { setCredentials({ username: "", password: "" }); await load(); } else if (next.error_code === "NEED_CAPTCHA") { setPreLogin(await api.preLoginEdu(connection.id)); } else if (next.error_message) setConnectionError(next.error_message); } catch (error) { setConnectionError(errorText(error, "登录失败")); } finally { setBusy(""); } }
  async function submitCaptcha(event) { event.preventDefault(); if (!connection?.id || !preLogin) return; setBusy("captcha"); try { const next = await api.continueEduConnection(connection.id, { username: credentials.username, password: credentials.password, captcha, pre_login_token: preLogin.pre_login_token, action: "SUBMIT_WITH_CAPTCHA" }); setConnection(next); setPreLogin(null); setCaptcha(""); if (next.state === "connected") { setCredentials({ username: "", password: "" }); await load(); } else if (next.error_message) setConnectionError(next.error_message); } catch (error) { setConnectionError(errorText(error, "验证码验证失败")); } finally { setBusy(""); } }
  async function loadSchedule() { setScheduleLoading(true); try { setSchedule(asItems(await api.getScheduleItems())); } catch (error) { setNotice(errorText(error, "课表加载失败")); } finally { setScheduleLoading(false); } }
  async function unbind() { if (!window.confirm("确认解绑教务账号？")) return; try { await api.unbindEdu(); setConnection(null); await load(); } catch (error) { setNotice(errorText(error, "解绑失败")); } }
  const bound = state.binding?.connection_status === "active";
  const records = state.records;

  return <PageFrame eyebrow="Academic / Integration" title="教务中心" description="连接自己的教务账号，用于同步课程、课表、成绩和考试。" actions={<Button variant="secondary" icon="PhArrowClockwise" onClick={load}>刷新状态</Button>}>
    <Notice message={state.error || notice || connectionError} tone={state.error || connectionError || notice?.includes("失败") ? "error" : "info"} />
    <div className="stack reveal"><EduStatus status={state.status} binding={state.binding} connection={connection} />
      {state.status?.status === "university_required" && <Panel><SectionHeading title="先选择你的大学" detail="不同学校使用不同教务连接器" /><div className="university-picker"><div className="filter-bar"><input className="search-field" value={universityQuery} onChange={(event) => setUniversityQuery(event.target.value)} placeholder="搜索大学名称" /><Button variant="secondary" onClick={searchUniversities}>搜索</Button></div>{universities.length ? <div className="list-stack">{universities.map((university) => <button className="list-row" key={university.id} onClick={() => pickUniversity(university.id)}><span className="university-logo">{String(university.name || "大").slice(0, 1)}</span><span className="row-copy"><strong>{university.name}</strong><small>{university.code || university.province || "选择此大学"}</small></span><Icon name="PhCaretRight" /></button>)}</div> : <p className="muted-copy">输入关键词后搜索可用学校。</p>}</div></Panel>}
      {bound ? <Panel><SectionHeading title="教务账号已绑定" detail="密码不会展示在页面中" /><div className="detail-grid"><div><span>Provider</span><strong>{state.binding.provider || "—"}</strong></div><div><span>外部学号</span><strong>{state.binding.external_student_id || "—"}</strong></div><div><span>最后同步</span><strong>{formatDate(state.binding.last_synced_at)}</strong></div><div><span>同步状态</span><strong>{state.binding.last_sync_status || "—"}</strong></div></div>{state.binding.last_error && <Notice message={`上次错误：${state.binding.last_error}`} tone="error" />}<div className="form-footer"><Button disabled={Boolean(busy)} onClick={() => sync("profile")}>{busy === "profile" ? "同步中…" : "同步基本信息"}</Button><Button disabled={Boolean(busy)} onClick={() => sync("schedule")}>{busy === "schedule" ? "同步中…" : "同步课表"}</Button><Button disabled={Boolean(busy)} onClick={() => sync("grade")}>{busy === "grade" ? "同步中…" : "同步成绩"}</Button><Button disabled={Boolean(busy)} onClick={() => sync("exam")}>{busy === "exam" ? "同步中…" : "同步考试"}</Button><Button variant="danger" disabled={Boolean(busy)} onClick={unbind}>解绑</Button></div></Panel> : <>
        <Panel><SectionHeading title="连接教务系统" detail="输入网址后自动识别系统类型" /><form className="form-grid" onSubmit={probeAndConnect}><div className="field full"><label htmlFor="edu-url">教务系统地址</label><input id="edu-url" type="url" value={manualUrl} onChange={(event) => setManualUrl(event.target.value)} placeholder="https://jwxt.yourschool.edu.cn/" required /></div><div className="form-footer field full"><Button disabled={busy === "probe"}>{busy === "probe" ? "检测中…" : "检测并创建连接"}</Button></div></form>{probe && <div className="status-hero"><strong>检测结果：{probe.provider || "未知系统"}</strong><small>可访问：{probe.reachable ? "是" : "否"} · 登录方式：{probe.suggested_login_mode === "client_webview" ? "浏览器登录" : "账号密码登录"}</small></div>}</Panel>
        {connection?.login_execution_mode === "backend_http" && <Panel><SectionHeading title="提交教务账号" detail="密码仅用于本次认证，不会明文保存" /><form className="form-grid" onSubmit={submitCredentials}><div className="field"><label>学号</label><input value={credentials.username} onChange={(event) => setCredentials({ ...credentials, username: event.target.value })} autoComplete="username" required /></div><div className="field"><label>密码</label><input type="password" value={credentials.password} onChange={(event) => setCredentials({ ...credentials, password: event.target.value })} autoComplete="current-password" required /></div><div className="form-footer field full"><Button disabled={busy === "credentials"}>{busy === "credentials" ? "验证中…" : "登录并绑定"}</Button></div></form></Panel>}
        {preLogin && <Panel><SectionHeading title="完成验证码" detail="学校登录页要求图片验证码" /><form className="form-grid" onSubmit={submitCaptcha}>{preLogin.captcha_image_base64 && <img className="captcha-image" src={`data:image/png;base64,${preLogin.captcha_image_base64}`} alt="教务系统验证码" />}<div className="field"><label>验证码</label><input value={captcha} onChange={(event) => setCaptcha(event.target.value)} autoComplete="off" required /></div><div className="form-footer field full"><Button disabled={busy === "captcha"}>{busy === "captcha" ? "验证中…" : "提交验证码"}</Button><Button type="button" variant="secondary" onClick={async () => setPreLogin(await api.preLoginEdu(connection.id))}>刷新验证码</Button></div></form></Panel>}
      </>}
      {bound && <><div className="grid grid-2"><SchedulePanel items={schedule} onOpen={setSelectedCourse} action={<Button variant="quiet" onClick={loadSchedule}>{scheduleLoading ? "加载中…" : "加载课表"}</Button>} /><Panel><SectionHeading title="最近同步" detail="教务系统操作记录" />{records.length ? <div className="list-stack">{records.map((record, index) => <div className="list-row" key={record.id || `${record.created_at}-${index}`}><span className="row-icon tone-green"><Icon name="PhArrowsClockwise" /></span><span className="row-copy"><strong>{record.sync_type || record.type || "同步"}</strong><small>{record.message || record.status || "操作完成"}</small></span><span className="row-meta">{formatDate(record.created_at || record.started_at)}</span></div>)}</div> : <div className="inline-empty">暂无同步记录</div>}</Panel></div></>}
    </div>
    {selectedCourse && <Modal title={selectedCourse.course_name || selectedCourse.name || "课程详情"} onClose={() => setSelectedCourse(null)}><dl className="detail-list"><dt>地点</dt><dd>{selectedCourse.location || "待定"}</dd><dt>教师</dt><dd>{selectedCourse.teacher || selectedCourse.teacher_name || "待定"}</dd><dt>周次</dt><dd>{selectedCourse.weeks || selectedCourse.week_text || "待定"}</dd><dt>节次</dt><dd>{selectedCourse.start_section ? `第${selectedCourse.start_section}-${selectedCourse.end_section || selectedCourse.start_section}节` : "待定"}</dd></dl></Modal>}
  </PageFrame>;
}

export function ChaoxingPage() {
  const [state, setState] = useState({ loading: true, error: "", data: {} });
  const [form, setForm] = useState({ username: "", password: "" });
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  async function load() { setState({ loading: true, error: "", data: {} }); try { setState({ loading: false, error: "", data: await api.getChaoxingStatus() }); } catch (error) { setState({ loading: false, error: errorText(error), data: {} }); } }
  useEffect(() => { load(); }, []);
  async function login(event) { event.preventDefault(); setBusy("login"); try { await api.loginChaoxing(form.username, form.password); setForm({ username: "", password: "" }); setNotice("学习通登录成功"); await load(); } catch (error) { setNotice(errorText(error, "学习通登录失败")); } finally { setBusy(""); } }
  async function sync() { setBusy("sync"); try { const result = await api.syncChaoxing(); const summary = chaoxingSyncSummary(result); setNotice(summary.complete ? `同步完成：${summary.courses} 门课程，${summary.notices} 条通知` : `同步部分完成：${summary.courses} 门课程，部分通知暂未同步`); await load(); } catch (error) { setNotice(errorText(error, "学习通同步失败")); } finally { setBusy(""); } }
  async function disconnect() { if (!window.confirm("确认断开学习通连接？")) return; setBusy("disconnect"); try { await api.disconnectChaoxing(); setNotice("已断开学习通连接"); await load(); } catch (error) { setNotice(errorText(error, "断开连接失败")); } finally { setBusy(""); } }
  const data = state.data || {};
  const connected = isChaoxingConnected(data);
  const canLogin = !connected && data.status !== "unavailable";
  const statusMessage = { expired: "学习通登录已过期，请重新连接。", verification_required: "学习通需要重新验证，请重新连接。", unavailable: "暂时无法访问学习通，请稍后刷新重试。" }[data.status];
  const noticeTone = state.error || notice?.includes("失败") ? "error" : notice?.includes("部分") || data.status === "expired" || data.status === "unavailable" ? "warning" : "info";
  return <PageFrame eyebrow="Profile / Chaoxing" title="学习通管理" description="连接学习通后，将课程、作业和通知同步到 CampusMate。" actions={<BackLink to="/profile">返回个人中心</BackLink>}><Notice message={state.error || notice || statusMessage} tone={noticeTone} />{state.loading ? <div className="state-card loading-state"><span className="loading-orb" /><p>正在读取学习通状态…</p></div> : <div className="stack reveal"><Panel className="integration-card"><div className="integration-icon"><Icon name="PhLink" size={29} /></div><div><span className="eyebrow">CHAOXING LIVE</span><h2>{connected ? "学习通已连接" : data.status === "expired" ? "学习通连接已过期" : "连接你的学习通账号"}</h2><p>{data.username ? `账号：${data.username}` : data.status === "unavailable" ? "学习通暂时不可用，请稍后重试。" : "账号信息只用于登录和同步。"}</p></div>{connected && <Button variant="secondary" icon="PhArrowClockwise" disabled={Boolean(busy)} onClick={sync}>{busy === "sync" ? "同步中…" : "立即同步"}</Button>}{connected && <Button variant="danger" disabled={Boolean(busy)} onClick={disconnect}>断开连接</Button>}{canLogin && <form className="bind-form" onSubmit={login}><input required value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} placeholder="学习通账号" autoComplete="username" /><input required type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} placeholder="密码" autoComplete="current-password" /><Button disabled={busy === "login"}>{busy === "login" ? "登录中…" : data.status === "expired" ? "重新连接" : "连接学习通"}</Button></form>}{data.status === "unavailable" && <Button variant="secondary" icon="PhArrowClockwise" onClick={load}>重新检查</Button>}</Panel>{connected && <div className="stat-grid"><div className="stat-card tone-blue"><span className="stat-icon"><Icon name="PhBookOpen" /></span><div><span>课程</span><strong>{data.courses ?? 0}</strong><small>已同步课程</small></div></div><div className="stat-card tone-orange"><span className="stat-icon"><Icon name="PhClipboardText" /></span><div><span>教师</span><strong>{data.teachers ?? 0}</strong><small>课程教师</small></div></div><div className="stat-card tone-violet"><span className="stat-icon"><Icon name="PhCheckSquare" /></span><div><span>待办</span><strong>{data.pending_assignments ?? 0}</strong><small>待处理作业</small></div></div><div className="stat-card tone-green"><span className="stat-icon"><Icon name="PhBell" /></span><div><span>通知</span><strong>{data.notices ?? 0}</strong><small>已同步通知</small></div></div></div>}<Panel><SectionHeading title="同步说明" detail="CampusMate 会复用后端连接，不在浏览器保存密码" /><p className="muted-copy">首次连接可能需要几秒钟完成登录和课程抓取。同步过程中可以继续浏览其他页面，完成后首页的课程、作业和通知会自动更新。</p>{data.last_synced_at && <small className="muted-copy">最近同步：{formatDate(data.last_synced_at)}</small>}</Panel></div>}</PageFrame>;
}
