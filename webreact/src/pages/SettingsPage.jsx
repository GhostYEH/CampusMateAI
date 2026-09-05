import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../data/api.js";
import { useApp } from "../app/AppContext.jsx";
import { BackLink, Button } from "../components/Primitives.jsx";
import { Icon } from "../components/Icon.jsx";
import SettingsSection from "../components/settings/SettingsSection.jsx";
import SettingToggle from "../components/settings/SettingToggle.jsx";
import { persistPreference, readPreferences } from "../features/settings/settingsPreferences.js";

const errorText = (error) => error?.response?.data?.detail || error?.response?.data?.message || error?.message || "资料加载失败，请重试";

function profileValue(profile, session, key) {
  return profile?.[key] || session?.[key] || "—";
}

function AccountRow({ label, value }) {
  return <div className="settings-account-row"><dt>{label}</dt><dd>{value}</dd></div>;
}

function SelectOption({ label, detail, value, options, onChange }) {
  return <div className="settings-option settings-select-option">
    <div className="settings-option-copy"><strong>{label}</strong><small>{detail}</small></div>
    <select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)}>
      {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
    </select>
  </div>;
}

export default function SettingsPage() {
  const navigate = useNavigate();
  const { session, logout, reduceMotion, setReduceMotion, dashboardStyle, setDashboardStyle } = useApp();
  const [preferences, setPreferences] = useState(() => readPreferences());
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadProfile() {
    setLoading(true);
    setError("");
    try {
      setProfile(await api.getProfile());
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadProfile();
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (preferences.theme === "auto") root.removeAttribute("data-theme");
    else root.dataset.theme = preferences.theme;
    return () => root.removeAttribute("data-theme");
  }, [preferences.theme]);

  function showSaved() {
    setNotice("设置已保存");
    window.setTimeout(() => setNotice(""), 1600);
  }

  function updatePreference(name, value) {
    setPreferences((current) => ({ ...current, [name]: value }));
    persistPreference(name, value);
    showSaved();
  }

  function updateMotion(value) {
    setReduceMotion(value);
    updatePreference("reduceMotion", value);
  }

  function updateDashboard(value) {
    setDashboardStyle(value);
    showSaved();
  }

  function signOut() {
    logout();
    navigate("/login", { replace: true });
  }

  const displayName = profile?.display_name || profile?.name || session?.name || "同学";
  const college = profileValue(profile, session, "college");
  const major = profileValue(profile, session, "major");

  return <main id="main-content" className="page-frame react-settings-page">
    <section className="settings-hero">
      <div className="settings-hero-copy">
        <BackLink to="/profile">返回个人中心</BackLink>
        <span className="settings-kicker">PREFERENCES / 偏好设置</span>
        <h1>设置</h1>
        <p>管理账号、通知、隐私和界面偏好，设置会保存在当前设备。</p>
      </div>
      <Button variant="secondary" icon="PhArrowClockwise" onClick={loadProfile} disabled={loading}>{loading ? "读取中…" : "刷新"}</Button>
    </section>

    {notice && <div className="settings-status" role="status"><Icon name="PhCheckCircle" size={16} />{notice}</div>}
    {error && <div className="settings-status settings-status-error" role="alert"><Icon name="PhWarningCircle" size={16} /><span>{error}</span><Button variant="quiet" onClick={loadProfile}>重试</Button></div>}

    <div className="settings-sections reveal">
      <SettingsSection icon="PhUser" title="账号设置" detail="查看你的身份信息与登录状态" className="settings-account">
        {loading ? <div className="settings-loading" role="status">正在读取账号资料…</div> : <dl className="settings-account-list">
          <AccountRow label="姓名" value={displayName} />
          <AccountRow label="学号" value={profileValue(profile, session, "student_number")} />
          <AccountRow label="学院" value={college} />
          <AccountRow label="专业" value={major} />
          <AccountRow label="邮箱" value={profileValue(profile, session, "email")} />
        </dl>}
        <div className="settings-account-actions"><Button variant="secondary" icon="PhPencil" onClick={() => navigate("/profile")}>编辑资料</Button><Button variant="danger" icon="PhSignOut" onClick={signOut}>退出登录</Button></div>
      </SettingsSection>

      <SettingsSection icon="PhBell" tone="violet" title="通知设置" detail={`选择希望接收的提醒类型${displayName ? ` · ${displayName}` : ""}`} className="settings-notifications">
        <SettingToggle label="考试提醒" detail="临近考试时提示复习与考试信息" value={preferences.examReminder} onChange={(value) => updatePreference("examReminder", value)} />
        <SettingToggle label="待办到期" detail="个人待办与作业临近截止时提醒" value={preferences.taskDue} onChange={(value) => updatePreference("taskDue", value)} />
        <SettingToggle label="校园通知" detail="接收校园公告与课程通知" value={preferences.announcementNotify} onChange={(value) => updatePreference("announcementNotify", value)} />
        <SettingToggle label="首页通知提醒" detail="在首页显示未读通知提示" value={preferences.noticeReminder} onChange={(value) => updatePreference("noticeReminder", value)} />
      </SettingsSection>

      <SettingsSection icon="PhShieldCheck" tone="orange" title="隐私设置" detail="控制个人状态的可见范围" className="settings-privacy">
        <SettingToggle label="分享专注统计" detail="允许在社区展示你的专注成就" value={preferences.shareFocusStats} onChange={(value) => updatePreference("shareFocusStats", value)} />
        <SettingToggle label="显示在线状态" detail="让好友看到你正在使用 CampusMate" value={preferences.showOnline} onChange={(value) => updatePreference("showOnline", value)} />
      </SettingsSection>

      <SettingsSection icon="PhPaintBrush" tone="blue" title="界面偏好" detail="按照你的使用习惯调整工作台显示方式" className="settings-display">
        <SelectOption label="首页视图" detail="工作台适合快速处理，成长地图更强调进度" value={dashboardStyle} options={[{ value: "classic", label: "工作台" }, { value: "gamified", label: "成长地图" }]} onChange={updateDashboard} />
        <SelectOption label="主题" detail="跟随系统或固定使用浅色、深色模式" value={preferences.theme} options={[{ value: "auto", label: "跟随系统" }, { value: "light", label: "浅色" }, { value: "dark", label: "深色" }]} onChange={(value) => updatePreference("theme", value)} />
        <SettingToggle label="减少动效" detail="关闭页面进入和装饰性动画，降低视觉干扰" value={reduceMotion} onChange={updateMotion} />
        <SettingToggle label="紧凑列表" detail="减少长列表的垂直间距，提升信息密度" value={preferences.compactList} onChange={(value) => updatePreference("compactList", value)} />
        <SettingToggle label="自动播放语音" detail="允许 AI 助手自动播放回答语音" value={preferences.autoplayVoice} onChange={(value) => updatePreference("autoplayVoice", value)} />
      </SettingsSection>
    </div>
  </main>;
}
