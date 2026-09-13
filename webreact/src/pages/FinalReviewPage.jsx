import { useEffect, useState } from "react";
import * as api from "../data/api.js";
import { agentApi } from "../data/agentApi.js";
import { AsyncState, Button, PageFrame, Panel, SectionHeading } from "../components/Primitives.jsx";

const messageOf = (error) => error?.response?.data?.message || error?.message || "操作失败";

export default function FinalReviewPage() {
  const [exams, setExams] = useState([]); const [campaigns, setCampaigns] = useState([]); const [examId, setExamId] = useState("");
  const [active, setActive] = useState(null); const [plan, setPlan] = useState(null); const [agenda, setAgenda] = useState(null);
  const [loading, setLoading] = useState(true); const [busy, setBusy] = useState(""); const [notice, setNotice] = useState("");
  async function load() { setLoading(true); try { const [examRows, campaignRows] = await Promise.all([api.getExams(), agentApi.listCampaigns()]); setExams(examRows); setCampaigns(campaignRows); setExamId((value) => value || examRows[0]?.id || ""); } catch (e) { setNotice(messageOf(e)); } finally { setLoading(false); } }
  useEffect(() => { load(); }, []);
  async function create() { if (!examId) return; setBusy("create"); try { const row = await agentApi.createCampaign({ exam_id: examId, daily_capacity_minutes: 90 }); setActive(row); setCampaigns(await agentApi.listCampaigns()); } catch (e) { setNotice(messageOf(e)); } finally { setBusy(""); } }
  async function generate() { setBusy("generate"); try { setPlan(await agentApi.generatePlan(active.campaign_id)); } catch (e) { setNotice(messageOf(e)); } finally { setBusy(""); } }
  async function activate() { setBusy("activate"); try { const row = await agentApi.activatePlan(active.campaign_id); setActive(row); setAgenda(await agentApi.todayAgenda(active.campaign_id)); } catch (e) { setNotice(messageOf(e)); } finally { setBusy(""); } }
  async function complete(itemId) { await agentApi.completeDailyItem(itemId); setAgenda(await agentApi.todayAgenda(active.campaign_id)); }
  return <PageFrame className="agent-workspace" eyebrow="Agent / Final Review" title="期末复习指挥台" description="计划版本由服务器生成并审核，激活后才会写入今日任务。">
    {notice && <div className="page-notice notice-error" role="alert">{notice}</div>}
    <AsyncState loading={loading}><div className="agent-grid"><Panel><SectionHeading title="选择正式考试" detail="只接受教务侧服务器考试 ID" /><select aria-label="选择考试" value={examId} onChange={(e) => setExamId(e.target.value)}><option value="">请选择</option>{exams.map((exam) => <option key={exam.id} value={exam.id}>{exam.course_name || "考试"} · {exam.exam_date}</option>)}</select><Button disabled={!examId || busy} onClick={create}>{busy === "create" ? "创建中…" : "创建复习活动"}</Button><div className="agent-list">{campaigns.map((item) => <button key={item.campaign_id} onClick={() => setActive(item)}><strong>{item.exam_id}</strong><small>{item.status} · 版本 {item.active_version || "未激活"}</small></button>)}</div></Panel>
    <Panel><SectionHeading title="版本化复习计划" detail="旧版本保留，未经激活不会创建任务" />{active ? <><div className="agent-badges"><span>{active.status}</span><span>每日 {active.daily_capacity_minutes} 分钟</span></div><Button disabled={busy} onClick={generate}>生成新版本</Button>{plan && <pre className="agent-json">{JSON.stringify(plan.content, null, 2)}</pre>}<Button disabled={!plan || busy} onClick={activate}>{busy === "activate" ? "激活中…" : "审核并激活"}</Button></> : <p className="muted-copy">选择或创建一个复习活动。</p>}</Panel>
    <Panel className="agent-wide"><SectionHeading title="今日议程" detail="完成状态会同步回服务器和个人任务" />{agenda?.items?.length ? <div className="agent-list">{agenda.items.map((item) => <button key={item.item_id} disabled={item.status === "COMPLETED"} onClick={() => complete(item.item_id)}><strong>{item.title}</strong><small>{item.duration_minutes} 分钟 · {item.status}</small></button>)}</div> : <p className="muted-copy">激活计划后显示今日议程。</p>}</Panel></div></AsyncState>
  </PageFrame>;
}
