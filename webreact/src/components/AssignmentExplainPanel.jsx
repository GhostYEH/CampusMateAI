import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../data/api.js";
import { Button, Panel, SectionHeading } from "./Primitives.jsx";
import { Icon } from "./Icon.jsx";

const clip = (value, max) => String(value || "").trim().slice(0, max);

export default function AssignmentExplainPanel({ assignment, answer = "" }) {
  const navigate = useNavigate();
  const [confirmed, setConfirmed] = useState(false); const [includeAnswer, setIncludeAnswer] = useState(false); const [goal, setGoal] = useState(""); const [difficulty, setDifficulty] = useState("");
  const [messages, setMessages] = useState([]); const [sending, setSending] = useState(false); const [error, setError] = useState(""); const [notice, setNotice] = useState("");
  const aborter = useRef(null);
  const courseId = assignment?.course_id || assignment?.courseId || "";

  useEffect(() => () => aborter.current?.abort(), []);

  function contextPreview() {
    return { title: clip(assignment?.title, 200), description: clip(assignment?.description, 1200), deadline: assignment?.deadline || "未设置", attachments: (assignment?.attachments || []).map((file) => clip(file.original_filename, 160)).filter(Boolean) };
  }

  async function explain() {
    if (!courseId || sending) return;
    setSending(true); setError(""); setNotice("");
    const context = contextPreview(); const ownAnswer = includeAnswer ? clip(answer, 4000) : "";
    const prompt = ["请在当前已授权课程上下文中讲解这份作业。只提供理解、步骤拆解和检查思路，不代替提交。", `作业标题：${context.title}`, `作业说明：${context.description || "暂无说明"}`, `截止时间：${context.deadline}`, `授权附件文件名：${context.attachments.length ? context.attachments.join("、") : "无"}`, goal.trim() ? `我的目标：${clip(goal, 500)}` : "", difficulty.trim() ? `我卡住的地方：${clip(difficulty, 800)}` : "", ownAnswer ? `我明确授权把自己的答案草稿作为讲解材料：${ownAnswer}` : "不要使用我的答案正文。"].filter(Boolean).join("\n");
    const pending = { role: "assistant", text: "", streaming: true }; setMessages([pending]); aborter.current = new AbortController();
    try {
      let streamFailed = false;
      await api.chatStream(prompt, { courseId, conversationId: `assignment-${assignment.id}-${Date.now()}`, signal: aborter.current.signal, onChunk: (chunk) => setMessages((current) => [{ ...pending, text: `${current[0]?.text || ""}${chunk}` }]), onDone: () => setMessages((current) => current.map((item) => ({ ...item, streaming: false }))), onError: (failure) => { streamFailed = true; setError(failure?.message || "讲解服务暂时不可用。"); } });
      if (!streamFailed) setNotice("讲解已完成；如需互动课堂，请再次确认生成。");
    } catch (failure) { if (failure?.name !== "AbortError") setError(failure?.message || "讲解失败。"); } finally { setSending(false); }
  }

  async function generateClassroom() {
    if (!courseId || sending) return;
    setSending(true); setError("");
    try { const result = await api.generateInteractiveClassroom(courseId, { mode: "explain", learning_objective: `围绕作业「${clip(assignment.title, 160)}」进行步骤讲解${goal.trim() ? `：${clip(goal, 300)}` : ""}`, current_difficulty: clip(difficulty, 600) }); const sessionId = result?.session?.session_id || result?.session?.id; setNotice(sessionId ? "互动课堂已开始生成。" : "互动课堂请求已提交。"); if (sessionId) navigate(`/courses/${courseId}?tab=mentoring&session=${encodeURIComponent(sessionId)}`); }
    catch (failure) { setError(failure?.response?.data?.detail || failure?.message || "互动课堂生成失败，作业页面未受影响。"); } finally { setSending(false); }
  }

  if (!courseId) return <Panel><SectionHeading title="magic'class 作业讲解" detail="课程归属无法确认" /><p className="muted-copy">当前作业缺少已授权课程上下文，暂不开放讲解入口。</p></Panel>;
  return <Panel className="assignment-explain-panel"><SectionHeading title="让 magic'class 讲解这份作业" detail="默认只发送作业元数据，不发送你的答案正文。" />{!confirmed ? <><p className="muted-copy">可先预览将要授权的上下文，再决定是否开始文字讲解或生成互动课堂。</p><Button icon="PhSparkle" onClick={() => setConfirmed(true)}>查看上下文并确认</Button></> : <><div className="assignment-explain-context"><strong>将使用</strong><ul><li>作业：{clip(assignment.title, 200)}</li><li>说明：{clip(assignment.description, 400) || "暂无说明"}</li><li>截止：{assignment.deadline || "未设置"}</li><li>附件：{assignment.attachments?.length ? assignment.attachments.map((file) => file.original_filename).join("、") : "无"}</li></ul></div><label className="field"><span>我希望重点解决</span><input value={goal} onChange={(event) => setGoal(event.target.value)} maxLength={500} placeholder="例如：看懂题意并列出解题步骤" /></label><label className="field"><span>我目前卡在</span><textarea value={difficulty} onChange={(event) => setDifficulty(event.target.value)} maxLength={800} placeholder="可选，不填写也能开始讲解" /></label><label className="interactive-checkbox"><input type="checkbox" checked={includeAnswer} onChange={(event) => setIncludeAnswer(event.target.checked)} disabled={!answer.trim()} /><span>明确授权把我的答案草稿作为讲解材料</span></label>{includeAnswer && <p className="openmaic-hint">已选择发送答案草稿，仅用于本次讲解，不会用于提交或修改作业。</p>}<div className="form-footer"><Button disabled={sending} onClick={explain}>{sending ? "处理中…" : "确认并开始文字讲解"}</Button><Button variant="secondary" disabled={sending} onClick={generateClassroom}>确认生成互动课堂</Button></div>{messages.map((message, index) => <div className="assignment-explain-result" key={index} role="status"><Icon name="PhChatCircleText" size={18} /><p>{message.text || (message.streaming ? "正在生成讲解…" : "暂无讲解内容")}</p></div>)}{notice && <p className="openmaic-hint" role="status">{notice}</p>}{error && <p className="openmaic-hint openmaic-hint--error" role="alert">{error}</p>}</>}</Panel>;
}
