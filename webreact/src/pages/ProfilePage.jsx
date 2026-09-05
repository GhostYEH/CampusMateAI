import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../data/api.js";
import { useApp } from "../app/AppContext.jsx";
import { Icon } from "../components/Icon.jsx";
import "../styles/student-redesign.css";
import "../styles/student-profile-reference.css";
import "../styles/profile-patch.css";

const TABS = [
  { key: "overview", label: "资料编辑" },
  { key: "tools", label: "我的工具" },
  { key: "settings", label: "设置" },
];

const QUICK_TOOLS = [
  { label: "我的大学", detail: "选择或切换大学身份", icon: "PhBuildings", path: "/university", tone: "indigo" },
  { label: "教务系统", detail: "查看绑定与同步状态", icon: "PhStudent", path: "/profile/academic", tone: "teal" },
  { label: "学习通同步", detail: "连接账号并同步课程作业", icon: "PhGraduationCap", path: "/profile/chaoxing", tone: "blue" },
  { label: "学习陪伴", detail: "开始一段专注时光", icon: "PhChartLineUp", path: "/study", tone: "violet" },
  { label: "课程表", detail: "查看本周课程安排", icon: "PhCalendarBlank", path: "/courses", tone: "blue" },
  { label: "待办事项", detail: "管理待完成任务", icon: "PhCheckSquare", path: "/tasks", tone: "green" },
  { label: "通知整理", detail: "查看重要校园信息", icon: "PhBell", path: "/notifications", tone: "indigo" },
  { label: "AI 校园助手", detail: "获取校园问题建议", icon: "PhRobot", path: "/counselor", tone: "teal" },
];

const PROFILE_LINKS = [
  { label: "我的收藏", detail: "查看保存的帖子与空间", icon: "PhBookmarkSimple", path: "/profile/favorites", tone: "violet" },
  { label: "课程资料", detail: "从课程详情继续查看附件", icon: "PhFiles", path: "/profile/files", tone: "blue" },
  { label: "学习记录", detail: "回看专注时长与学习轨迹", icon: "PhChartLineUp", path: "/profile/learning", tone: "indigo" },
  { label: "校园身份卡", detail: "快速出示校园身份信息", icon: "PhIdentificationCard", path: "/profile/id-card", tone: "blue" },
];

function formatSessionDate(value) {
  if (!value) return "时间待记录";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function ProfilePage() {
  const navigate = useNavigate();
  const { pendingCount, reduceMotion, setReduceMotion } = useApp();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [profile, setProfile] = useState({});
  const [dashboard, setDashboard] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [tab, setTab] = useState("overview");
  const [editing, setEditing] = useState(false);
  const [noticeReminder, setNoticeReminder] = useState(() => localStorage.getItem("campus_notice_reminder") !== "false");
  const [form, setForm] = useState({ display_name: "", college: "", major: "", grade: "", email: "" });

  const displayName = profile.display_name || profile.username || "同学";
  const initial = displayName.slice(0, 1);
  const identityLine = [profile.college, profile.major, profile.grade].filter(Boolean).join(" · ") || "完善你的校园资料，让陪伴更贴合";

  const weekMinutes = useMemo(
    () => sessions.filter((item) => item.status === "completed").reduce((total, item) => total + Math.round((item.duration_seconds || 0) / 60), 0),
    [sessions],
  );

  const stats = [
    { label: "课程数量", value: dashboard?.enrolled_course_count ?? "—", hint: "本学期", icon: "PhBookOpen", tone: "blue" },
    { label: "待办事项", value: dashboard?.pending_assignment_count ?? pendingCount ?? "—", hint: "待完成", icon: "PhCheckSquare", tone: "green" },
    { label: "本周学习", value: weekMinutes ? `${(weekMinutes / 60).toFixed(1)}h` : "—", hint: "来自专注记录", icon: "PhChartLineUp", tone: "indigo" },
    { label: "成长积分", value: "—", hint: "暂未接入积分服务", icon: "PhSparkle", tone: "amber" },
  ];

  const details = [
    { label: "姓名", value: displayName, icon: "PhUser" },
    { label: "专业", value: profile.major || "暂未填写", icon: "PhNotebook" },
    { label: "学号", value: profile.student_number || "暂未填写", icon: "PhIdentificationCard" },
    { label: "年级", value: profile.grade || "暂未填写", icon: "PhGraduationCap" },
    { label: "学院", value: profile.college || "暂未填写", icon: "PhBuildings" },
    { label: "邮箱", value: profile.email || "暂未填写", icon: "PhEnvelopeSimple" },
  ];

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [profileData, dashboardData, sessionData] = await Promise.all([
        api.getProfile(),
        api.getDashboard().catch(() => null),
        api.getStudySessions().catch(() => []),
      ]);
      setProfile(profileData || {});
      setDashboard(dashboardData);
      setSessions(Array.isArray(sessionData) ? sessionData : sessionData?.items || []);
      setForm({
        display_name: profileData?.display_name || "",
        college: profileData?.college || "",
        major: profileData?.major || "",
        grade: profileData?.grade || "",
        email: profileData?.email || "",
      });
    } catch (err) {
      setError(err.response?.data?.detail || "个人资料加载失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }

  async function save(event) {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setError("");
    try {
      const next = await api.updateProfile(form);
      setProfile(next?.user || next || form);
      setEditing(false);
      setSaved("资料已保存");
      window.setTimeout(() => setSaved(""), 2200);
    } catch (err) {
      setError(err.response?.data?.detail || "资料保存失败，请重试。");
    } finally {
      setSaving(false);
    }
  }

  async function copyStudentNumber() {
    const value = profile.student_number;
    if (!value || !navigator.clipboard) return;
    await navigator.clipboard.writeText(value);
    setSaved("学号已复制");
    window.setTimeout(() => setSaved(""), 1800);
  }

  function toggleNoticeReminder(value) {
    setNoticeReminder(value);
    localStorage.setItem("campus_notice_reminder", String(value));
  }

  useEffect(() => { load(); }, []);

  return (
    <main className="student-page campus-redesign profile-redesign">
      <div className="redesign-heading">
        <div>
          <span className="redesign-kicker">PROFILE / 个人中心</span>
          <h1>个人中心</h1>
          <p>管理你的资料、学习工具入口和陪伴偏好设置。</p>
        </div>
        <button className="redesign-button secondary" disabled={loading} onClick={load}>
          <Icon name="PhArrowClockwise" className={loading ? "spinning" : ""} />刷新
        </button>
      </div>

      {error && (
        <div className="redesign-alert error">
          <Icon name="PhWarningCircle" />
          <span>{error}</span>
          <button onClick={load}>重试</button>
        </div>
      )}

      {loading ? (
        <div className="profile-loading" aria-label="正在加载个人中心">
          <div className="profile-loading-banner"></div>
          <div className="profile-loading-grid"><i></i><i></i><i></i></div>
        </div>
      ) : (
        <>
          <header className="profile-banner redesign-panel">
            <div className="profile-banner-main">
              <div className="profile-avatar-wrap">
                <div className="profile-avatar">{initial}</div>
                <span className="profile-avatar-check"><Icon name="PhCheck" size={13} weight="bold" /></span>
              </div>
              <div className="profile-intro">
                <div className="profile-name-row">
                  <h2>{displayName}</h2>
                  <span className="profile-tag">本科生</span>
                </div>
                <div className="profile-meta-row profile-primary-meta">
                  <span><Icon name="PhUser" />{profile.student_number || "学号待完善"}<button aria-label="复制学号" onClick={copyStudentNumber}><Icon name="PhCopy" size={13} /></button></span>
                  <span><Icon name="PhBuildings" />{profile.college || "学院待完善"}</span>
                  <span><Icon name="PhBookOpen" />{profile.major || "专业待完善"}</span>
                </div>
                <div className="profile-secondary-meta">
                  <span><Icon name="PhGraduationCap" />{profile.grade || "年级待完善"}</span>
                  <span className="profile-status">账号状态：正常</span>
                </div>
              </div>
            </div>
            <div className="profile-stat-grid">
              {stats.map((item) => (
                <article key={item.label} className="profile-stat">
                  <span className={`profile-stat-icon ${item.tone}`}><Icon name={item.icon} size={20} /></span>
                  <span><small>{item.label}</small><strong>{item.value}</strong><em>{item.hint}</em></span>
                </article>
              ))}
            </div>
            <img className="profile-banner-art" src="/assets/campusmate-hero-illustration.png" alt="" aria-hidden="true" />
          </header>

          <nav className="redesign-tabs" aria-label="个人中心分区">
            {TABS.map((item) => (
              <button key={item.key} className={tab === item.key ? "active" : ""} onClick={() => setTab(item.key)}>{item.label}</button>
            ))}
          </nav>

          {tab === "overview" && (
            <section className="profile-overview-grid">
              <div className="profile-main-column">
                <article className="redesign-panel profile-info-panel">
                  <div className="redesign-panel-head">
                    <h2>基本资料</h2>
                    <div className="panel-head-actions">
                      {saved && <span className="redesign-status success"><Icon name="PhCheckCircle" />{saved}</span>}
                      {!editing && <button className="text-action" onClick={() => setEditing(true)}><Icon name="PhPencil" />编辑资料</button>}
                    </div>
                  </div>
                  {!editing ? (
                    <dl className="profile-detail-list">
                      {details.map((item) => (
                        <div key={item.label}>
                          <Icon name={item.icon} size={18} />
                          <dt>{item.label}</dt>
                          <dd>{item.value}</dd>
                        </div>
                      ))}
                    </dl>
                  ) : (
                    <form className="profile-edit-form" onSubmit={save}>
                      <label>姓名<input value={form.display_name} autoComplete="name" onChange={(e) => setForm({ ...form, display_name: e.target.value })} /></label>
                      <label>学号<input value={profile.student_number || "暂未填写"} disabled /></label>
                      <label>学院<input value={form.college} autoComplete="organization" onChange={(e) => setForm({ ...form, college: e.target.value })} /></label>
                      <label>专业<input value={form.major} onChange={(e) => setForm({ ...form, major: e.target.value })} /></label>
                      <label>年级<input value={form.grade} onChange={(e) => setForm({ ...form, grade: e.target.value })} /></label>
                      <label>邮箱<input value={form.email} type="email" autoComplete="email" onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
                      <div className="profile-edit-actions"><button type="button" className="redesign-button secondary" onClick={() => setEditing(false)}>取消</button><button className="redesign-button primary" disabled={saving}>{saving ? "保存中…" : "保存资料"}</button></div>
                    </form>
                  )}
                </article>

                <article className="redesign-panel profile-tools-panel">
                  <div className="redesign-panel-head"><h2>快捷入口</h2></div>
                  <div className="profile-quick-grid">
                    {QUICK_TOOLS.map((item) => (
                      <button key={item.path} className="profile-quick-card" onClick={() => navigate(item.path)}>
                        <span className={`profile-quick-icon ${item.tone}`}><Icon name={item.icon} size={27} /></span>
                        <span><strong>{item.label}</strong><small>{item.detail}</small></span>
                      </button>
                    ))}
                  </div>
                </article>
              </div>

              <aside className="profile-side-column">
                <article className="redesign-panel campus-card" role="button" tabIndex={0} onClick={() => navigate("/profile/id-card")} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); navigate("/profile/id-card"); } }}>
                  <div className="redesign-panel-head"><h2>校园身份卡</h2></div>
                  <div className="campus-card-body">
                    <div className="campus-card-seal">{initial}</div>
                    <div><strong>{displayName} <em>本科生</em></strong><span>{profile.student_number || "学号待完善"}</span><span>{identityLine}</span></div>
                    <Icon name="PhQrCode" className="campus-card-check" size={24} weight="bold" />
                    <Icon name="PhSealCheck" className="campus-card-watermark" size={120} weight="duotone" />
                  </div>
                </article>

                <article className="redesign-panel activity-panel">
                  <div className="redesign-panel-head"><h2>最近活动</h2><button className="link-action" onClick={() => navigate("/study")}>查看学习记录 <Icon name="PhArrowRight" size={14} /></button></div>
                  {sessions.length ? (
                    <div className="profile-activity-list">
                      {sessions.slice(0, 4).map((session) => (
                        <div key={session.id}><span className="activity-dot"></span><span><strong>{session.goal || "完成了一次学习陪伴"}</strong><small>{formatSessionDate(session.started_at)} · {session.status === "completed" ? `${Math.round((session.duration_seconds || 0) / 60)} 分钟` : "进行中"}</small></span></div>
                      ))}
                    </div>
                  ) : (
                    <div className="profile-mini-empty"><Icon name="PhClockCounterClockwise" size={19} /><span>还没有学习活动记录，开始一次专注后会显示在这里。</span></div>
                  )}
                </article>
              </aside>
            </section>
          )}

          {tab === "tools" && (
            <section className="profile-tools-view">
              <article className="redesign-panel tools-intro"><div><span className="redesign-label">YOUR TOOLBOX</span><h2>把校园服务整理成自己的工作台</h2><p>从课程、通知到专注记录，常用入口都可以在这里快速打开。</p></div><button className="redesign-button primary" onClick={() => navigate("/home")}><Icon name="PhHouse" />回到首页</button></article>
              <div className="profile-tools-large-grid">
                {QUICK_TOOLS.map((item) => (
                  <button key={item.path} className="redesign-panel profile-tool-large" onClick={() => navigate(item.path)}><span className={`profile-quick-icon ${item.tone}`}><Icon name={item.icon} size={24} /></span><span><strong>{item.label}</strong><small>{item.detail}</small></span><Icon name="PhArrowUpRight" size={17} /></button>
                ))}
              </div>
              <div className="profile-tools-section-head"><div><span className="redesign-label">PROFILE SHORTCUTS</span><h2>个人中心入口</h2></div><span>把资料、记录和服务放在同一个地方</span></div>
              <div className="profile-tools-large-grid profile-links-grid">
                {PROFILE_LINKS.map((item) => (
                  <button key={item.path} className="redesign-panel profile-tool-large" onClick={() => navigate(item.path)}><span className={`profile-quick-icon ${item.tone}`}><Icon name={item.icon} size={24} /></span><span><strong>{item.label}</strong><small>{item.detail}</small></span><Icon name="PhArrowUpRight" size={17} /></button>
                ))}
              </div>
            </section>
          )}

          {tab === "settings" && (
            <section className="redesign-panel profile-settings-panel">
              <div className="redesign-panel-head"><div><span className="redesign-label">PREFERENCES</span><h2>陪伴偏好</h2></div><span className="panel-hint">设置会保存在当前设备</span></div>
              <div className="preference-list">
                <div className="preference-row"><span className="preference-icon blue"><Icon name="PhSparkle" /></span><span><strong>减少动态效果</strong><small>关闭页面进入动画和不必要的过渡，适合需要更稳定界面的场景。</small></span><button className={`preference-toggle ${reduceMotion ? "on" : ""}`} aria-pressed={reduceMotion} onClick={() => setReduceMotion(!reduceMotion)}><i></i></button></div>
                <div className="preference-row"><span className="preference-icon green"><Icon name="PhBell" /></span><span><strong>截止提醒</strong><small>控制待办与作业的提醒展示，具体通知能力以学校数据源为准。</small></span><button className={`preference-toggle ${noticeReminder ? "on" : ""}`} aria-pressed={noticeReminder} onClick={() => toggleNoticeReminder(!noticeReminder)}><i></i></button></div>
              </div>
              <div className="settings-links"><button onClick={() => navigate("/study")}><Icon name="PhChartLineUp" />查看学习统计</button><button onClick={() => navigate("/counselor")}><Icon name="PhRobot" />打开 AI 校园助手</button></div>
            </section>
          )}
        </>
      )}
    </main>
  );
}
