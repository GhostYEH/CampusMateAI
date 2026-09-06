import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { marked } from "marked";
import * as api from "../data/api.js";
import { useApp } from "../app/AppContext.jsx";
import { itemsOf } from "../data/contracts.js";
import DigitalHumanPanel from "../components/DigitalHumanPanel.jsx";
import { Icon } from "../components/Icon.jsx";
import RippleDistortion from "../components/RippleDistortion.jsx";
import { useDigitalHumanSpeech } from "../hooks/useDigitalHumanSpeech.js";

const suggestionSets = [
  ["期末考试如何高效复习？", "我要申请课程重修，需要准备什么？", "帮我把这周的任务排个轻重缓急", "校园卡充值和退款流程是怎样的？"],
  ["校园卡丢失了，怎么挂失补办？", "如何申请奖学金？", "宿舍断电了找谁报修？", "图书馆借阅规则是什么？"],
];
const fallbackSessions = [
  { id: "sample-main", title: "期末复习计划怎么安排？", displayTime: "10:24" },
  { id: "sample-card", title: "校园卡丢失了，怎么办？", displayTime: "昨天" },
  { id: "sample-scholar", title: "如何申请奖学金？", displayTime: "昨天" },
  { id: "sample-library", title: "图书馆借阅规则是什么？", displayTime: "08/10" },
  { id: "sample-dorm", title: "宿舍断电了找谁报修？", displayTime: "08/09" },
];
const actionSuggestions = [
  ["生成个性化复习计划", "PhCalendarBlank"],
  ["制定每日任务清单", "PhClipboardText"],
  ["推荐复习资料", "PhBookOpen"],
  ["更多建议", "PhSquaresFour"],
];
const sampleQuestion = "期末考试周的复习计划应该怎么安排更高效？";
const sampleAnswer = `期末考试周的复习建议如下，结合近期课程安排与常见复习方法，帮助你高效备考：

1. **制定复习计划：** 按科目和难度分配时间，优先复习高难度与高分值内容。
2. **梳理知识框架：** 先搭建各科知识框架，再填充细节，形成完整体系。
3. **真题与错题：** 近年真题至少做两遍，错题本定期回顾避免重复错误。
4. **合理作息：** 保持规律作息，每天保证 7–8 小时睡眠，适度运动放松。

需要我帮你生成一份个性化复习计划表吗？`;
const sampleSources = [
  { title: "教务处：期末考试安排通知" },
  { title: "学习建议中心：高效复习指南" },
  { title: "心理中心：考试周压力法" },
];
const studyOverview = [
  { label: "已完成任务", value: "5 / 7", icon: "PhChecks", tone: "cyan" },
  { label: "学习时长", value: "12.6 小时", icon: "PhTimer", tone: "amber" },
  { label: "连续学习", value: "6 天", icon: "PhFire", tone: "violet" },
];
const reminders = [
  { title: "高等数学期末考试（还有 5 天）", time: "09:00", tone: "amber" },
  { title: "提交课程论文初稿（3号楼 302）", time: "14:00", tone: "cyan" },
  { title: "英语口语小组会议", time: "20:00", tone: "violet" },
];

function readSessions() {
  try { return JSON.parse(localStorage.getItem("campus_counselor_sessions") || "[]"); } catch { return []; }
}

function renderMarkdown(value) {
  const html = marked.parse(value || "", { breaks: true, gfm: true });
  if (typeof DOMParser === "undefined") return String(value || "");
  const documentValue = new DOMParser().parseFromString(html, "text/html");
  documentValue.querySelectorAll("script,style,iframe,object,embed,form,link,meta").forEach((node) => node.remove());
  documentValue.querySelectorAll("*").forEach((node) => [...node.attributes].forEach((attribute) => { if (attribute.name.toLowerCase().startsWith("on")) node.removeAttribute(attribute.name); }));
  documentValue.querySelectorAll("a").forEach((node) => {
    try { const url = new URL(node.getAttribute("href"), window.location.href); if (!["http:", "https:"].includes(url.protocol)) node.removeAttribute("href"); else { node.setAttribute("rel", "noreferrer noopener"); node.setAttribute("target", "_blank"); } } catch { node.removeAttribute("href"); }
  });
  return documentValue.body.innerHTML;
}

function sessionTime(item) {
  if (item.displayTime) return item.displayTime;
  const date = new Date(item.updatedAt);
  return Number.isNaN(date.getTime()) ? "刚刚" : date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

export default function CounselorPage() {
  const { reduceMotion } = useApp();
  const [messages, setMessages] = useState(() => [{ role: "user", text: sampleQuestion }, { role: "assistant", text: sampleAnswer }]);
  const [sources, setSources] = useState(sampleSources);
  const [sessions, setSessions] = useState(readSessions);
  const [conversationId, setConversationId] = useState("sample-main");
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const [deepThinking, setDeepThinking] = useState(true);
  const [attachment, setAttachment] = useState(null);
  const [notice, setNotice] = useState("");
  const [suggestionPage, setSuggestionPage] = useState(0);
  const [showAllSessions, setShowAllSessions] = useState(false);
  const [policyDialog, setPolicyDialog] = useState("");
  const chatRef = useRef(null);
  const attachmentInput = useRef(null);
  const aborter = useRef(null);
  const promptHandled = useRef(false);
  const shouldAutoScroll = useRef(false);
  const sourcesRef = useRef(sampleSources);
  const digitalHuman = useDigitalHumanSpeech({ onNotice: setNotice });
  const { stop: stopSpeech, speak: speakSpeech } = digitalHuman;
  const suggestions = suggestionSets[suggestionPage];
  const recentTasksRef = useRef([]);

  useEffect(() => {
    let alive = true;
    api.getTasks({ status: "pending", page_size: 8 }).then((value) => {
      if (alive) recentTasksRef.current = itemsOf(value).slice(0, 8).map((item) => ({ title: item.title, deadline: item.deadline, description: item.description, source_name: item.source_name }));
    }).catch(() => {});
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    if (shouldAutoScroll.current && chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [messages, sources]);

  const displaySessions = useMemo(() => {
    const stored = sessions.filter((item) => item.id !== "sample-main");
    const all = [...fallbackSessions, ...stored];
    return showAllSessions ? all : all.slice(0, 5);
  }, [sessions, showAllSessions]);

  const persistSession = useCallback((nextMessages, id, nextSources) => {
    const first = nextMessages.find((item) => item.role === "user");
    if (!first || !id) return;
    setSessions((current) => {
      const next = [{ id, title: first.text.slice(0, 24), updatedAt: new Date().toISOString(), messages: nextMessages, sources: nextSources }, ...current.filter((item) => item.id !== id)].slice(0, 12);
      localStorage.setItem("campus_counselor_sessions", JSON.stringify(next));
      return next;
    });
  }, []);

  const send = useCallback(async (value = input) => {
    const text = value.trim();
    if (!text || sending) return;
    stopSpeech();
    const id = conversationId && !conversationId.startsWith("sample-") ? conversationId : `web-${Date.now()}`;
    const nextMessages = [...messages, { role: "user", text }, { role: "assistant", text: "", streaming: true }];
    const pending = nextMessages[nextMessages.length - 1];
    shouldAutoScroll.current = true;
    sourcesRef.current = [];
    setConversationId(id); setMessages(nextMessages); setInput(""); setSources([]); setSending(true); setNotice("");
    aborter.current = new AbortController();
    try {
      await api.chatStream(text, {
        conversationId: id,
        recentTasks: recentTasksRef.current,
        webSearch: webSearchEnabled,
        attachment,
        signal: aborter.current.signal,
        onSources: (items) => { sourcesRef.current = items || []; setSources(sourcesRef.current); },
        onChunk: (chunk) => { pending.text += chunk; setMessages((current) => [...current.slice(0, -1), { ...pending }]); },
        onDone: (meta) => {
          pending.streaming = false;
          const nextId = meta?.conversation_id || id;
          setConversationId(nextId);
          setMessages((current) => [...current.slice(0, -1), { ...pending }]);
          persistSession([...messages, { role: "user", text }, { ...pending }], nextId, sourcesRef.current);
          speakSpeech(pending.text);
        },
        onError: (error) => {
          pending.streaming = false;
          pending.text = pending.text || "校园知识库暂时未连接，我已记录你的问题，请稍后再试。";
          setMessages((current) => [...current.slice(0, -1), { ...pending }]);
          persistSession([...messages, { role: "user", text }, { ...pending }], id, sourcesRef.current);
          setNotice(error?.message || "AI 暂时无法回应");
        },
      });
    } finally { setSending(false); aborter.current = null; }
  }, [attachment, conversationId, input, messages, persistSession, sending, speakSpeech, stopSpeech, webSearchEnabled]);

  useEffect(() => {
    const prompt = new URLSearchParams(window.location.search).get("prompt");
    if (prompt && !promptHandled.current) { promptHandled.current = true; window.setTimeout(() => send(prompt), 0); }
  }, [send]);
  useEffect(() => () => aborter.current?.abort(), []);

  function seedSample() { stopSpeech(); sourcesRef.current = sampleSources; setConversationId("sample-main"); setMessages([{ role: "user", text: sampleQuestion }, { role: "assistant", text: sampleAnswer }]); setSources(sampleSources); setInput(""); setNotice(""); }
  function newSession() { stopSpeech(); sourcesRef.current = []; setConversationId(`web-${Date.now()}`); setMessages([]); setSources([]); setInput(""); setAttachment(null); setNotice("已创建新对话"); window.requestAnimationFrame(() => document.querySelector(".counselor-reference textarea")?.focus()); }
  function restoreSession(item) {
    stopSpeech();
    shouldAutoScroll.current = true;
    if (item.id === "sample-main") { seedSample(); return; }
    sourcesRef.current = item.sources || [];
    setConversationId(item.id); setMessages(item.messages?.length ? item.messages : [{ role: "user", text: item.title }, { role: "assistant", text: `关于“${item.title}”，我可以为你查询学校规定、整理办理步骤，并生成一份行动清单。` }]); setSources(item.sources || []); setNotice("");
  }
  async function copyText(text, message = "内容已复制") { try { await navigator.clipboard?.writeText(text); setNotice(message); } catch { setNotice("当前浏览器不支持自动复制"); } }
  async function turnToTask() { const last = [...messages].reverse().find((item) => item.role === "assistant" && item.text); if (!last) return; try { await api.createTask({ title: last.text.replace(/[#*\n]/g, " ").trim().slice(0, 80) || "AI 建议", description: last.text, source_name: "AI 校园助手对话", source_text: last.text }); setNotice("已保存为个人待办"); } catch (error) { setNotice(error?.message || "待办保存失败"); } }
  async function selectAttachment(event) {
    const file = event.target.files?.[0]; event.target.value = ""; if (!file) return;
    if (file.size > 1_000_000 || (!(["text/plain", "text/markdown", "application/json", "text/csv"].includes(file.type) && !/\.(txt|md|csv|json)$/i.test(file.name)))) { setNotice("当前支持 1 MB 以内的 TXT、Markdown、CSV 和 JSON 文本附件"); return; }
    setAttachment({ name: file.name, type: file.type || "text/plain", size: file.size, content: await file.text() }); setNotice(`已选择附件：${file.name}`);
  }
  const lastAssistant = [...messages].reverse().find((item) => item.role === "assistant" && item.text);

  return <main className="counselor-reference">
    <section className="counselor-reference-hero"><RippleDistortion className="counselor-ripple" src="/assets/counselor-campus-hero-reference.png" brushSize={110} strength={0.2} swirl={0.7} rings={4} spacing={8} glint={0.35} tint="#3168da" tintAmount={0.12} grayscale={false} highlightColor="#b9f4ff" trigger="both" quality="medium" enabled={!reduceMotion} /><div className="counselor-reference-hero-wash" /><div className="counselor-reference-hero-copy"><span className="counselor-hero-kicker">CAMPUS INTELLIGENCE · READY TO HELP</span><div className="counselor-reference-title"><h1>AI校园助手</h1><Icon name="PhSparkle" size={31} /></div><p>你的专属校园智能伙伴，随时为你解答疑问，<br />提供学习与生活的贴心帮助。</p></div></section>
    {notice && <div className="counselor-toast" role="status"><Icon name="PhInfo" size={16} />{notice}</div>}
    <section className="counselor-reference-grid">
      <aside className="counselor-reference-left">
        <section className="counselor-panel history-panel counselor-session-panel"><div className="counselor-panel-head"><h2>会话记录</h2><button className="new-chat" type="button" onClick={newSession}><Icon name="PhPlus" size={16} />新建对话</button></div><div className="reference-session-list">{displaySessions.map((session) => <button type="button" key={session.id} className={session.id === conversationId ? "active" : ""} onClick={() => restoreSession(session)}><Icon name="PhChatCircleText" size={15} /><strong>{session.title}</strong><small>{sessionTime(session)}</small></button>)}</div><button className="all-history" type="button" onClick={() => setShowAllSessions((value) => !value)}>{showAllSessions ? "收起记录" : "查看全部记录"}<Icon name={showAllSessions ? "PhCaretDown" : "PhCaretRight"} size={14} /></button></section>
        <section className="counselor-panel recommendations-panel"><div className="counselor-panel-head"><h2>推荐问题</h2><button className="switch-link" type="button" onClick={() => setSuggestionPage((value) => (value + 1) % suggestionSets.length)}>换一换 <Icon name="PhArrowClockwise" size={15} /></button></div><div className="reference-question-list">{suggestions.map((question) => <button type="button" key={question} onClick={() => send(question)}><Icon name="PhQuestion" size={14} /><span>{question}</span></button>)}</div></section>
      </aside>
      <section className="counselor-panel reference-chat-panel counselor-chat-panel"><header className="reference-chat-heading"><span className="reference-heading-avatar"><Icon name="PhRobot" size={20} /></span><div><h2>智能对话</h2><p>随时为你解答学习、生活、考试等各类问题</p></div><button type="button" className={deepThinking ? "reference-deep-thinking active" : "reference-deep-thinking"} aria-pressed={deepThinking} onClick={() => { setDeepThinking((value) => !value); setNotice(deepThinking ? "深度思考已关闭" : "深度思考已开启"); }}><Icon name="PhSparkle" size={15} />深度思考<Icon name="PhCaretDown" size={13} /></button><button type="button" className="reference-more" aria-label="更多对话选项"><Icon name="PhDotsThree" size={20} /></button></header><div ref={chatRef} className="reference-chat-messages">{!messages.length && <div className="empty-conversation"><span className="assistant-face"><Icon name="PhRobot" size={22} /></span><h2>开始一段新对话</h2><p>告诉我你想了解的校园问题，我会尽力帮你。</p></div>}{messages.map((message, index) => <div className={`reference-message ${message.role}`} key={`${conversationId}-${index}`}><div className="reference-avatar"><Icon name={message.role === "user" ? "PhUser" : "PhRobot"} size={19} /></div><div className="reference-bubble"><div className="markdown-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(message.text) }} />{message.streaming && <span className="typing-cursor">▍</span>}{message.role === "assistant" && index === messages.length - 1 && message.text && sources.length > 0 && <div className="reference-sources"><span>相关来源：</span>{sources.map((source) => <button type="button" key={source.document_id || source.title} onClick={() => copyText(source.title || source.document_title || "引用来源", "来源标题已复制")}>{source.title || source.document_title || "知识库资料"}<Icon name="PhArrowUpRight" size={12} /></button>)}</div>}</div></div>)}</div>
        <div className="reference-action-row">{actionSuggestions.map(([label, icon]) => <button type="button" key={label} onClick={() => send(label)}><Icon name={icon} size={18} />{label}</button>)}</div>
        <form className="reference-composer" onSubmit={(event) => { event.preventDefault(); send(); }}>{attachment && <div className="reference-attachment-chip"><Icon name="PhFileText" size={15} /><span>{attachment.name}</span><button type="button" aria-label="移除附件" onClick={() => { setAttachment(null); setNotice("附件已移除"); }}><Icon name="PhX" size={13} /></button></div>}<textarea value={input} disabled={sending} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); send(); } }} placeholder="请输入你的问题，Enter 发送；Shift + Enter 换行" aria-label="发送给 AI 的消息" /><div className="reference-composer-tools"><input ref={attachmentInput} className="reference-file-input" type="file" accept=".txt,.md,.csv,.json,text/plain,text/markdown,text/csv,application/json" onChange={selectAttachment} /><span><button type="button" onClick={() => attachmentInput.current?.click()}><Icon name="PhPaperclip" size={20} />附件</button><button type="button" className={webSearchEnabled ? "active" : ""} aria-pressed={webSearchEnabled} onClick={() => { setWebSearchEnabled((value) => !value); setNotice(webSearchEnabled ? "联网搜索已关闭" : "联网搜索已开启"); }}><Icon name="PhMagnifyingGlass" size={20} />联网搜索</button></span><button className="reference-send" type="submit" disabled={sending || !input.trim()}><Icon name="PhPaperPlaneTilt" size={20} />{sending ? "回答中" : "发送"}</button></div></form><footer className="reference-disclaimer"><span>AI 生成的内容仅供参考，请以学校官方信息为准</span><button type="button" onClick={() => setPolicyDialog("terms")}>服务条款</button><button type="button" onClick={() => setPolicyDialog("privacy")}>隐私政策</button></footer></section>
      <aside className="counselor-reference-right">
        <DigitalHumanPanel speaking={digitalHuman.speaking} muted={digitalHuman.muted} status={digitalHuman.unityStatus} canReplay={Boolean(digitalHuman.lastText)} onReady={digitalHuman.setUnityReady} onError={digitalHuman.setUnityError} onToggleMuted={digitalHuman.toggleMuted} onStop={digitalHuman.stop} onReplay={digitalHuman.replay} />
        <section className="counselor-panel counselor-study-status" aria-labelledby="study-status-title">
          <header className="counselor-panel-head"><h2 id="study-status-title">学习状态</h2><button type="button" className="switch-link">查看详情 <Icon name="PhCaretRight" size={14} /></button></header>
          <div className="counselor-study-overview"><div className="counselor-study-progress" aria-label="课程完成度 72%"><strong>72%</strong><span>课程完成度</span></div><div className="counselor-study-list">{studyOverview.map((item) => <div key={item.label} className={`counselor-study-item ${item.tone}`}><Icon name={item.icon} size={17} /><span>{item.label}</span><strong>{item.value}</strong></div>)}</div></div>
        </section>
        <section className="counselor-panel counselor-reminders" aria-labelledby="reminders-title">
          <header className="counselor-panel-head"><h2 id="reminders-title">今日提醒</h2><button type="button" className="switch-link">全部 <Icon name="PhCaretRight" size={14} /></button></header>
          <ul>{reminders.map((item) => <li key={item.title}><i className={item.tone} aria-hidden="true" /><span>{item.title}</span><time>{item.time}</time></li>)}</ul>
        </section>
        {lastAssistant && <section className="counselor-panel counselor-side-actions"><button type="button" onClick={turnToTask}><Icon name="PhCheckSquare" size={16} />把回答保存为待办</button><p>回答会保留在本地会话记录中，确认后再加入你的任务清单。</p></section>}
      </aside>
    </section>
    {policyDialog && <div className="reference-policy-overlay" role="presentation" onClick={(event) => event.target === event.currentTarget && setPolicyDialog("")}><section className="reference-policy-dialog" role="dialog" aria-modal="true" aria-label={policyDialog === "terms" ? "服务条款" : "隐私政策"}><header><h2>{policyDialog === "terms" ? "服务条款" : "隐私政策"}</h2><button type="button" aria-label="关闭弹窗" onClick={() => setPolicyDialog("")}><Icon name="PhX" size={19} /></button></header>{policyDialog === "terms" ? <><p>CampusMate AI 提供校园学习与生活信息辅助，生成内容仅供参考，正式安排请以学校官方通知为准。</p><p>请勿提交违法、有害或侵犯他人权益的内容。服务可能因校园系统维护而短暂不可用。</p></> : <><p>我们仅在完成当前功能所需范围内处理你的提问、会话记录和所选附件信息。</p><p>附件不会在未发送时上传；你可以随时移除附件或清除浏览器中的本地会话记录。</p></>}<button className="reference-policy-confirm" type="button" onClick={() => setPolicyDialog("")}>我知道了</button></section></div>}
  </main>;
}
