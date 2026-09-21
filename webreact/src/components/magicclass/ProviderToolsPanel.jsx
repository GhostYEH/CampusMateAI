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
  // 音色与风格指令要能真正传到上游。之前这里只发 `{ text }`，于是服务端的
  // `voice` / `instruction` 永远是默认值，界面上也就没有可调的地方。
  const [voice, setVoice] = React.useState("");
  const [instruction, setInstruction] = React.useState("");
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
    const result = await api.getMagicClassArtifact(courseId, job.artifact_id);
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
    const current = await api.getMagicClassJob(courseId, jobId);
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
        ? await api.synthesizeMagicClassTts(courseId, {
            text: value,
            // 空字符串表示"用服务端默认值"，不要发一个空白的 voice 覆盖它。
            ...(voice.trim() ? { voice: voice.trim() } : {}),
            ...(instruction.trim() ? { instruction: instruction.trim() } : {}),
            idempotencyKey: api.newIdempotencyKey(),
          })
        : await api.runMagicClassDiscussion(courseId, { prompt: value, idempotencyKey: api.newIdempotencyKey() });
      if (result?.job?.status === "completed") await readArtifact(result.job, kind, mine);
      else if (result?.job_id) await poll(result.job_id, kind, mine);
      else throw new Error("受管服务未返回任务编号");
    } catch (failure) {
      if (mine === epoch.current) { setError(messageOf(failure, "Provider 任务失败")); setBusy(false); }
    }
  }

  return <Panel className="magicclass-provider-tools">
    <SectionHeading title="课堂工具" detail="使用当前课程上下文；Provider 不可用时入口不会出现" />
    {error ? <p className="magicclass-hint magicclass-hint--error" role="alert">{error}</p> : null}
    {notice ? <p className="magicclass-hint" role="status">{notice}</p> : null}
    {canTts ? <form className="magicclass-command" onSubmit={(event) => { event.preventDefault(); void submit("tts"); }}>
      <label className="magicclass-command__input"><Icon name="PhSpeakerHigh" size={18} /><input value={text} onChange={(event) => setText(event.target.value)} maxLength={20000} placeholder="输入要听的讲解文字" aria-label="语音讲解文字" /></label>
      {/* 音色与风格留空即用服务端配置的默认值；填了才随请求发出去。 */}
      <label className="magicclass-command__input"><input value={voice} onChange={(event) => setVoice(event.target.value)} maxLength={80} placeholder="音色（留空用默认）" aria-label="语音音色" /></label>
      <label className="magicclass-command__input"><input value={instruction} onChange={(event) => setInstruction(event.target.value)} maxLength={2000} placeholder="风格指令（留空用默认）" aria-label="语音风格指令" /></label>
      <Button type="submit" disabled={busy || !text.trim()}>生成语音</Button>
    </form> : null}
    {audioUrl ? <audio className="magicclass-provider-tools__audio" controls src={audioUrl} aria-label="语音讲解播放器" /> : null}
    {canDiscussion ? <form className="magicclass-command" onSubmit={(event) => { event.preventDefault(); void submit("discussion"); }}>
      <label className="magicclass-command__input"><Icon name="PhChats" size={18} /><input value={prompt} onChange={(event) => setPrompt(event.target.value)} maxLength={4000} placeholder="让三位角色讨论一个概念" aria-label="圆桌讨论问题" /></label>
      <Button type="submit" variant="secondary" disabled={busy || !prompt.trim()}>开始圆桌讨论</Button>
    </form> : null}
    {messages.length ? <ol className="magicclass-provider-tools__messages" aria-label="圆桌讨论记录">{messages.map((item, index) => <li key={`${item.agent || "agent"}-${index}`}><strong>{item.agent || "智能体"}</strong><span>{item.content || ""}</span></li>)}</ol> : null}
    {busy ? <p className="magicclass-hint" role="status">Provider 任务处理中，可稍后刷新查看结果…</p> : null}
  </Panel>;
}
