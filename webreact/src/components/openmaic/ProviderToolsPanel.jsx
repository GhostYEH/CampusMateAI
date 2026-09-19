import React from "react";
import { Button, Panel, SectionHeading } from "../Primitives.jsx";
import { Icon } from "../Icon.jsx";
import * as api from "../../data/api.js";

function messageOf(error, fallback) {
  return error?.response?.data?.detail || error?.response?.data?.message || error?.message || fallback;
}

/** Provider-backed tools live in the native workspace and only render when the
 * gateway reports the matching capability. Jobs and artifacts remain course
 * scoped; the browser never receives provider configuration. */
export default function ProviderToolsPanel({ courseId, canTts = false, canDiscussion = false }) {
  const [text, setText] = React.useState("");
  const [prompt, setPrompt] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");
  const [notice, setNotice] = React.useState("");
  const [audioUrl, setAudioUrl] = React.useState("");
  const [messages, setMessages] = React.useState([]);
  const timer = React.useRef(null);
  const epoch = React.useRef(0);

  React.useEffect(() => () => {
    epoch.current += 1;
    if (timer.current) window.clearTimeout(timer.current);
    if (audioUrl && typeof URL !== "undefined") URL.revokeObjectURL(audioUrl);
  }, [audioUrl]);

  if (!canTts && !canDiscussion) return null;

  async function readArtifact(job, kind, mine) {
    if (mine !== epoch.current || !job?.artifact_id) return;
    const result = await api.getOpenMAICArtifact(courseId, job.artifact_id);
    if (mine !== epoch.current) return;
    if (kind === "tts") {
      const nextUrl = URL.createObjectURL(result.blob);
      setAudioUrl((old) => {
        if (old) URL.revokeObjectURL(old);
        return nextUrl;
      });
      setNotice("语音讲解已生成，可直接播放。");
      return;
    }
    const payload = JSON.parse(await result.blob.text());
    setMessages(Array.isArray(payload.messages) ? payload.messages : []);
    setNotice("圆桌讨论已生成。");
  }

  async function poll(jobId, kind, mine) {
    const current = await api.getOpenMAICJob(courseId, jobId);
    if (mine !== epoch.current || current?.id !== jobId) return;
    if (["queued", "running"].includes(current.status)) {
      timer.current = window.setTimeout(() => void poll(jobId, kind, mine), 800);
      return;
    }
    if (current.status !== "completed") throw new Error(current.error_code || "Provider 任务未完成");
    await readArtifact(current, kind, mine);
    if (mine === epoch.current) setBusy(false);
  }

  async function submit(kind) {
    const value = (kind === "tts" ? text : prompt).trim();
    if (!value || busy) return;
    const mine = (epoch.current += 1);
    setBusy(true); setError(""); setNotice(""); setMessages([]);
    try {
      const result = kind === "tts"
        ? await api.synthesizeOpenMAICTts(courseId, { text: value, idempotencyKey: api.newIdempotencyKey() })
        : await api.runOpenMAICDiscussion(courseId, { prompt: value, idempotencyKey: api.newIdempotencyKey() });
      if (result?.job?.status === "completed") await readArtifact(result.job, kind, mine);
      else if (result?.job_id) await poll(result.job_id, kind, mine);
      else throw new Error("受管服务未返回任务编号");
    } catch (failure) {
      if (mine === epoch.current) { setError(messageOf(failure, "Provider 任务失败")); setBusy(false); }
    }
  }

  return <Panel className="openmaic-provider-tools">
    <SectionHeading title="课堂工具" detail="使用当前课程上下文；Provider 不可用时入口不会出现" />
    {error ? <p className="openmaic-hint openmaic-hint--error" role="alert">{error}</p> : null}
    {notice ? <p className="openmaic-hint" role="status">{notice}</p> : null}
    {canTts ? <form className="openmaic-command" onSubmit={(event) => { event.preventDefault(); void submit("tts"); }}>
      <label className="openmaic-command__input"><Icon name="PhSpeakerHigh" size={18} /><input value={text} onChange={(event) => setText(event.target.value)} maxLength={20000} placeholder="输入要听的讲解文字" aria-label="语音讲解文字" /></label>
      <Button type="submit" disabled={busy || !text.trim()}>生成语音</Button>
    </form> : null}
    {audioUrl ? <audio className="openmaic-provider-tools__audio" controls src={audioUrl} aria-label="语音讲解播放器" /> : null}
    {canDiscussion ? <form className="openmaic-command" onSubmit={(event) => { event.preventDefault(); void submit("discussion"); }}>
      <label className="openmaic-command__input"><Icon name="PhChats" size={18} /><input value={prompt} onChange={(event) => setPrompt(event.target.value)} maxLength={4000} placeholder="让三位角色讨论一个概念" aria-label="圆桌讨论问题" /></label>
      <Button type="submit" variant="secondary" disabled={busy || !prompt.trim()}>开始圆桌讨论</Button>
    </form> : null}
    {messages.length ? <ol className="openmaic-provider-tools__messages" aria-label="圆桌讨论记录">{messages.map((item, index) => <li key={`${item.agent || "agent"}-${index}`}><strong>{item.agent || "智能体"}</strong><span>{item.content || ""}</span></li>)}</ol> : null}
    {busy ? <p className="openmaic-hint" role="status">Provider 任务处理中，可稍后刷新查看结果…</p> : null}
  </Panel>;
}
