import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { marked } from "marked";
import * as api from "../data/api.js";
import { useApp } from "../app/AppContext.jsx";
import { itemsOf } from "../data/contracts.js";
import DigitalHumanPanel from "../components/DigitalHumanPanel.jsx";
import ClassroomProposalCard from "../components/interactive/ClassroomProposalCard.jsx";
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
// 课程上下文下的动态推荐问题：只做通用措辞，不冒充真实的掌握状态。
const courseContextSuggestions = [
  "讲解这门课当前最重要的知识点",
  "根据我的掌握情况安排复习",
  "帮我设计一次可视化学习",
  "为这门课生成自测",
  "哪些内容适合用互动课堂学习",
];
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
  const { reduceMotion, session } = useApp();
  // 课堂任务的作用域身份：账号切换后绝不恢复上一个账号的任务与深链。
  const classroomIdentity =
    session?.id || session?.user_id || session?.username || "anon";
  const [classroomProposal, setClassroomProposal] = useState(null);
  const [messages, setMessages] = useState(() => {
    const hasInitialPrompt = new URLSearchParams(typeof window !== "undefined" ? window.location.search : "").get("prompt");
    return hasInitialPrompt ? [] : [{ role: "user", text: sampleQuestion }, { role: "assistant", text: sampleAnswer }];
  });
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
  // 会话代次：新建/切换会话、退出课程辅导时 +1，作废所有在途的流式回写。
  // 只靠 aborter.abort() 不够 —— 已经收到的分片仍会继续写进**新**会话的最后一条消息。
  const chatEpoch = useRef(0);
  const promptHandled = useRef(false);
  const shouldAutoScroll = useRef(false);
  const sourcesRef = useRef(sampleSources);
  const digitalHuman = useDigitalHumanSpeech({ onNotice: setNotice });
  const { stop: stopSpeech, speak: speakSpeech } = digitalHuman;
  const suggestions = suggestionSets[suggestionPage];
  const recentTasksRef = useRef([]);
  // 课程辅导上下文：从 URL 查询参数读取（?course=<id>&prompt=<初始问题>）。
  const [courseId, setCourseId] = useState(() => new URLSearchParams(typeof window !== "undefined" ? window.location.search : "").get("course") || null);
  const [workspaceId] = useState(() => new URLSearchParams(typeof window !== "undefined" ? window.location.search : "").get("workspace") || null);
  const [courseName, setCourseName] = useState("");

  // 课程页的输入工作区把"联网搜索"和"附件"通过 SPA 导航状态带过来，让那两个
  // 入口真的是同一件事，而不是点完就丢的空按钮。附件是 File 对象，只在内存里
  // 交接一次，随即清掉导航状态（刷新后不会复活）。
  useEffect(() => {
    const carried = typeof window !== "undefined" ? window.history?.state?.usr : null;
    if (!carried) return;
    if (carried.magicclassWebSearch) setWebSearchEnabled(true);
    if (carried.magicclassAttachment) setAttachment(carried.magicclassAttachment);
    if (typeof window !== "undefined" && window.history?.replaceState) {
      window.history.replaceState({ ...window.history.state, usr: null }, "");
    }
  }, []);

  useEffect(() => {
    if (!courseId) { setCourseName(""); return; }
    let alive = true;
    api.getCourse(courseId).then((data) => { if (alive) setCourseName(data?.name || data?.title || ""); }).catch(() => { if (alive) setCourseName(""); });
    return () => { alive = false; };
  }, [courseId]);

  const exitCourseContext = () => { resetConversationScope(); setCourseId(null); setCourseName(""); stopSpeech(); if (typeof window !== "undefined" && window.history) { const url = new URL(window.location.href); url.searchParams.delete("course"); url.searchParams.delete("prompt"); window.history.replaceState({}, "", url); } setNotice("已退出课程辅导"); };

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
      const next = [{ id, workspaceId, title: first.text.slice(0, 24), updatedAt: new Date().toISOString(), messages: nextMessages, sources: nextSources }, ...current.filter((item) => item.id !== id)].slice(0, 12);
      localStorage.setItem("campus_counselor_sessions", JSON.stringify(next));
      return next;
    });
  }, [workspaceId]);

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
    const myEpoch = chatEpoch.current;
    const isCurrentChat = () => myEpoch === chatEpoch.current;
    aborter.current = new AbortController();
    try {
      await api.chatStream(text, {
        conversationId: id,
        courseId: courseId || undefined,
        recentTasks: recentTasksRef.current,
        webSearch: webSearchEnabled,
        attachment,
        workspaceId: workspaceId,
        signal: aborter.current.signal,
        onSources: (items) => {
          if (!isCurrentChat()) return;
          sourcesRef.current = items || []; setSources(sourcesRef.current);
        },
        onChunk: (chunk) => {
          // 会话已经切走 → 迟到分片绝不能覆盖新会话的最后一条消息
          if (!isCurrentChat()) return;
          pending.text += chunk; setMessages((current) => [...current.slice(0, -1), { ...pending }]);
        },
        onDone: (meta) => {
          if (!isCurrentChat()) return;
          pending.streaming = false;
          const nextId = meta?.conversation_id || id;
          // CPM 只提建议：这里只保存提案，真正生成必须由学生点确认卡。
          const proposal = (meta?.suggested_actions || []).find(
            (item) => item?.type === "interactiveClassroomProposal",
          );
          setClassroomProposal(proposal?.data || null);
          setConversationId(nextId);
          setMessages((current) => [...current.slice(0, -1), { ...pending }]);
          persistSession([...messages, { role: "user", text }, { ...pending }], nextId, sourcesRef.current);
          speakSpeech(pending.text);
        },
        onError: (error) => {
          if (!isCurrentChat()) return;
          pending.streaming = false;
          pending.text = pending.text || "校园知识库暂时未连接，我已记录你的问题，请稍后再试。";
          setMessages((current) => [...current.slice(0, -1), { ...pending }]);
          persistSession([...messages, { role: "user", text }, { ...pending }], id, sourcesRef.current);
          setNotice(error?.message || "AI 暂时无法回应");
        },
      });
    } finally {
      // 只有仍属于本代次才清 loading：否则旧请求的 finally 会把新会话的发送态清掉
      if (isCurrentChat()) { setSending(false); aborter.current = null; }
    }
  }, [attachment, conversationId, input, messages, persistSession, sending, speakSpeech, stopSpeech, webSearchEnabled, courseId, workspaceId]);

  useEffect(() => {
    const prompt = new URLSearchParams(window.location.search).get("prompt");
    if (prompt && !promptHandled.current) { promptHandled.current = true; window.setTimeout(() => send(prompt), 0); }
  }, [send]);
  useEffect(() => () => aborter.current?.abort(), []);

  /** 切换会话作用域：作废在途流式回写，并停掉"回答中"状态。 */
  function resetConversationScope() {
    chatEpoch.current += 1;
    try { aborter.current?.abort(); } catch { /* 忽略 */ }
    aborter.current = null;
    setSending(false);
  }

  function seedSample() { resetConversationScope(); stopSpeech(); sourcesRef.current = sampleSources; setConversationId("sample-main"); setMessages([{ role: "user", text: sampleQuestion }, { role: "assistant", text: sampleAnswer }]); setSources(sampleSources); setInput(""); setNotice(""); }
  function newSession() { resetConversationScope(); stopSpeech(); sourcesRef.current = []; setConversationId(`web-${Date.now()}`); setMessages([]); setSources([]); setInput(""); setAttachment(null); setNotice("已创建新对话"); window.requestAnimationFrame(() => document.querySelector(".counselor-reference textarea")?.focus()); }
  function restoreSession(item) {
    resetConversationScope();
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
    {classroomProposal && <ClassroomProposalCard key={classroomProposal.proposal_id || classroomProposal.course_id} proposal={classroomProposal} identity={classroomIdentity} onOpenClassroom={(deepLink) => { if (deepLink) window.location.assign(deepLink); }} />}
      {courseId && <div className="counselor-course-context" role="status"><Icon name="PhBookOpen" size={18} /><span><strong>当前正在辅导：{courseName || "该课程"}</strong><small>{courseId} · {workspaceId ? `已绑定工作台 ${workspaceId}` : "已定向到课程上下文"}</small></span><button type="button" onClick={exitCourseContext}><Icon name="PhX" size={14} />退出课程辅导</button></div>}
    <section className="counselor-reference-grid">
      <aside className="counselor-reference-left">
        <section className="counselor-panel history-panel counselor-session-panel"><div className="counselor-panel-head"><h2>会话记录</h2><button className="new-chat" type="button" onClick={newSession}><Icon name="PhPlus" size={16} />新建对话</button></div><div className="reference-session-list">{displaySessions.map((session) => <button type="button" key={session.id} className={session.id === conversationId ? "active" : ""} onClick={() => restoreSession(session)}><Icon name="PhChatCircleText" size={15} /><strong>{session.title}</strong><small>{sessionTime(session)}</small></button>)}</div><button className="all-history" type="button" onClick={() => setShowAllSessions((value) => !value)}>{showAllSessions ? "收起记录" : "查看全部记录"}<Icon name={showAllSessions ? "PhCaretDown" : "PhCaretRight"} size={14} /></button></section>
        <section className="counselor-panel recommendations-panel"><div className="counselor-panel-head"><h2>{courseId ? "课程学习建议" : "推荐问题"}</h2><button className="switch-link" type="button" onClick={() => setSuggestionPage((value) => (value + 1) % suggestionSets.length)}>{courseId ? "换一批" : "换一换"} <Icon name="PhArrowClockwise" size={15} /></button></div><div className="reference-question-list">{(courseId ? courseContextSuggestions : suggestions).map((question) => <button type="button" key={question} onClick={() => send(question)}><Icon name="PhQuestion" size={14} /><span>{question}</span></button>)}</div></section>
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
