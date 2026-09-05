import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { BackLink, Button, LinkButton, PageFrame, Panel, SectionHeading } from "../components/Primitives.jsx";
import { Icon } from "../components/Icon.jsx";
import { formatDateTime } from "../utils/date.js";
import * as api from "../data/api.js";

const itemsOf = (value) => Array.isArray(value) ? value : value?.items || [];
const dateText = (value) => formatDateTime(value, { dateStyle: "medium", timeStyle: "short" }, "时间待记录");
const durationText = (item) => { const minutes = Math.round(Number(item.duration_seconds || 0) / 60); return minutes ? `${minutes} 分钟` : item.status === "completed" ? "已完成" : "进行中"; };

const sectionMeta = {
  favorites: ["SAVED / 收藏中心", "我的收藏", "把重要的帖子和校园内容留在这里，之后继续处理。", "PhBookmarkSimple"],
  files: ["FILES / 课程资料", "课程资料", "从课程详情进入课程附件，统一查看和下载学习资料。", "PhFiles"],
  learning: ["LEARNING / 学习记录", "学习记录", "回看每一次专注学习，把投入的时间变成清晰的进步。", "PhChartLineUp"],
  "id-card": ["IDENTITY / 校园身份", "校园身份卡", "集中查看你的校园身份信息，需要时快速出示或复制学号。", "PhIdentificationCard"],
};

function SecondaryNav({ active }) {
  return <nav className="secondary-nav" aria-label="个人中心二级导航">{Object.entries(sectionMeta).map(([key, value]) => <Link className={active === key ? "active" : ""} key={key} to={`/profile/${key}`}><Icon name={value[3]} size={16} />{value[1]}</Link>)}</nav>;
}

function Identity({ profile }) {
  const [notice, setNotice] = useState("");
  async function copy() { if (!profile.student_number || !navigator.clipboard) { setNotice("当前没有可复制的学号"); return; } await navigator.clipboard.writeText(profile.student_number); setNotice("学号已复制"); }
  return <div className="grid grid-2"><Panel className="identity-card"><span className="eyebrow">CAMPUSMATE IDENTITY</span><div className="identity-main"><span className="identity-seal">{String(profile.display_name || profile.username || "同").slice(0, 1)}</span><div><small>校园身份</small><h2>{profile.display_name || profile.username || "同学"}</h2><p>{profile.student_number || "学号待完善"}</p></div></div><div className="detail-grid"><div><span>所属学院</span><strong>{profile.college || "待完善"}</strong></div><div><span>专业方向</span><strong>{profile.major || "待完善"}</strong></div><div><span>年级</span><strong>{profile.grade || "待完善"}</strong></div><div><span>账户状态</span><strong>正常</strong></div></div><div className="form-footer"><Button icon="PhCopy" onClick={copy}>复制学号</Button></div><p className="muted-copy" role="status">{notice}</p></Panel><Panel><SectionHeading title="身份使用提示" detail="仅在需要核对身份时出示" /><div className="inline-empty"><Icon name="PhShieldCheck" size={42} /><span>请勿将身份卡截图分享给不熟悉的人，涉及账号安全时请联系学校服务中心。</span></div></Panel></div>;
}

export function ProfileSectionPage() {
  const { section = "favorites" } = useParams();
  const navigate = useNavigate();
  const meta = sectionMeta[section] || sectionMeta.favorites;
  const [profile, setProfile] = useState({});
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true); setError("");
    try {
      const user = await api.getProfile().catch(() => ({}));
      let next = [];
      if (section === "learning") next = itemsOf(await api.getStudySessions());
      setProfile(user); setRecords(next);
    } catch (cause) { setError(cause?.response?.data?.detail || cause?.message || "个人中心数据加载失败，请稍后重试。"); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, [section]);
  const title = meta[1];

  return <PageFrame eyebrow={meta[0]} title={title} description={meta[2]} actions={<><BackLink to="/profile">返回个人中心</BackLink><Button variant="secondary" icon="PhArrowClockwise" disabled={loading} onClick={load}>刷新</Button></>}>
    <SecondaryNav active={section} />
    {loading ? <div className="state-card loading-state"><span className="loading-orb" /><p>正在加载个人空间…</p></div> : error ? <div className="state-card error-state" role="alert"><Icon name="PhWarningCircle" size={24} /><p>{error}</p><Button variant="secondary" onClick={load}>重试</Button></div> : section === "id-card" ? <Identity profile={profile} /> : section === "learning" ? <Learning records={records} navigate={navigate} /> : section === "favorites" ? <Favorites navigate={navigate} /> : section === "files" ? <Files navigate={navigate} /> : <Favorites navigate={navigate} />}
  </PageFrame>;
}

function Learning({ records, navigate }) {
  const completed = records.filter((item) => item.status === "completed");
  const totalMinutes = completed.reduce((sum, item) => sum + Math.round(Number(item.duration_seconds || 0) / 60), 0);
  return <div className="stack"><div className="stat-grid"><div className="stat-card tone-violet"><span className="stat-icon"><Icon name="PhClock" /></span><div><span>累计专注</span><strong>{totalMinutes ? `${(totalMinutes / 60).toFixed(1)}h` : "—"}</strong><small>来自已完成记录</small></div></div><div className="stat-card tone-green"><span className="stat-icon"><Icon name="PhCheckCircle" /></span><div><span>完成次数</span><strong>{completed.length || "—"}</strong><small>保持自己的节奏</small></div></div><div className="stat-card tone-orange"><span className="stat-icon"><Icon name="PhChartLineUp" /></span><div><span>平均时长</span><strong>{completed.length ? `${Math.round(totalMinutes / completed.length)}m` : "—"}</strong><small>单次完成记录</small></div></div></div><Panel><SectionHeading title="专注记录" detail="每一次完成都会留下轨迹" action={<LinkButton to="/study" variant="quiet" icon="PhPlay">打开学习陪伴</LinkButton>} />{records.length ? <div className="list-stack">{records.slice().sort((a, b) => new Date(b.started_at || b.created_at || 0) - new Date(a.started_at || a.created_at || 0)).slice(0, 12).map((item) => <div className="list-row" key={item.id}><span className={`row-icon ${item.status === "completed" ? "tone-green" : ""}`}><Icon name={item.status === "completed" ? "PhCheck" : "PhClock"} /></span><span className="row-copy"><strong>{item.goal || "一次学习陪伴"}</strong><small>{dateText(item.started_at || item.created_at)} · {durationText(item)}</small></span><span className="row-meta">{item.status === "completed" ? "已完成" : "进行中"}</span></div>)}</div> : <div className="inline-empty"><Icon name="PhChartLineUp" size={42} /><span>还没有学习记录，去学习陪伴开始一次专注。</span><Button onClick={() => navigate("/study")}>开始专注</Button></div>}</Panel></div>;
}

function Favorites({ navigate }) { return <div className="stack"><div className="stat-grid"><div className="stat-card tone-violet"><span className="stat-icon"><Icon name="PhBookmarkSimple" /></span><div><span>已收藏内容</span><strong>—</strong><small>统一收藏服务待接入</small></div></div><div className="stat-card tone-blue"><span className="stat-icon"><Icon name="PhChatsCircle" /></span><div><span>论坛收藏</span><strong>—</strong><small>浏览帖子时可继续关注</small></div></div><div className="stat-card tone-green"><span className="stat-icon"><Icon name="PhBuildings" /></span><div><span>校园内容</span><strong>—</strong><small>在校园社区继续发现</small></div></div></div><Panel><div className="inline-empty"><Icon name="PhBookmarkSimple" size={42} /><span>收藏中心正在等你放入第一条内容</span><div className="form-footer"><Button onClick={() => navigate("/community")}>浏览校园论坛</Button></div></div></Panel></div>; }
function Files({ navigate }) { return <div className="stack"><Panel className="integration-card"><div className="integration-icon"><Icon name="PhFolderOpen" size={29} /></div><div><span className="eyebrow">COURSE MATERIALS</span><h2>课程资料从课程详情进入</h2><p>每门课程的公告、作业和附件会按照课程组织，进入课程后继续查看上下文。</p></div><Button onClick={() => navigate("/courses")}>打开我的课程</Button></Panel><Panel><div className="inline-empty"><Icon name="PhFiles" size={42} /><span>这里还没有独立文件，课程资料会保留在具体课程详情中。</span></div></Panel></div>; }
