import "../../styles/magicclass-classmates.css";
import React from "react";
import { MessageCircle, Send, Sparkles, Users, X } from "lucide-react";

import { cn } from "../../magicclass/utils/cn.js";

function initialOf(name) {
  return (name || "?").slice(0, 1);
}

/**
 * 原生课堂的同学条。
 *
 * 收起时只占一枚小徽章；展开后是同学发言 + 点名提问。没有同学开口时明确写
 * "这次先听大家说"，而不是空白；额度用完时关闭提问而不是让请求必然失败。
 */
export default function NativeClassmates({ classmates }) {
  const [open, setOpen] = React.useState(false);
  const [selected, setSelected] = React.useState("");
  const [draft, setDraft] = React.useState("");
  const { roster, messages, busy, error, silence, asking, left, budget, ask, retry } = classmates;
  const byId = new Map(roster.map((person) => [person.id, person]));
  const exhausted = left <= 0;
  const latest = messages[messages.length - 1] || null;

  const submit = (event) => {
    event.preventDefault();
    if (!selected || !draft.trim() || asking || exhausted) return;
    ask(selected, draft);
    setDraft("");
  };

  return <div className={cn("nc-root", open && "is-open")}>
    <button
      type="button"
      className="nc-toggle"
      onClick={() => setOpen((value) => !value)}
      aria-expanded={open}
      aria-label={open ? "收起 AI 同学" : "展开 AI 同学"}
    >
      {roster.length
        ? <span className="nc-squad" aria-hidden="true">
          {roster.slice(0, 4).map((person) => <i key={person.id} title={person.name}>{initialOf(person.name)}</i>)}
        </span>
        : <Users size={15} />}
      <span>学习小队</span>
      {roster.length ? <span className="nc-online">{roster.length} 在线</span> : null}
      {busy ? <span className="nc-dot is-thinking" aria-label="同学正在思考" /> : null}
      {comboLabel(left, budget)}
    </button>

    {!open && latest && <div className="nc-preview" aria-live="polite">
      <strong>{byId.get(latest.agentId)?.name || latest.agentId}</strong>
      <span>{latest.text}</span>
    </div>}

    {open && <aside className="nc-panel" aria-label="AI 同学">
      <header className="nc-head">
        <div>
          <strong>课堂同学</strong>
          <span>{exhausted ? "本节课额度已用完" : `剩余 ${left.toLocaleString()} tokens`}</span>
        </div>
        <button type="button" className="nc-close" onClick={() => setOpen(false)} aria-label="关闭同学面板">
          <X size={14} />
        </button>
      </header>

      <ul className="nc-roster">
        {roster.map((person) => <li key={person.id}>
          <button
            type="button"
            className={cn("nc-avatar", selected === person.id && "is-selected")}
            onClick={() => setSelected((current) => current === person.id ? "" : person.id)}
            title={person.persona}
          >
            <span>{initialOf(person.name)}</span>
            <small>{person.name}</small>
          </button>
        </li>)}
        {!roster.length && <li className="nc-empty">同学名单读取中…</li>}
      </ul>

      <div className="nc-feed" aria-live="polite">
        {busy && <p className="nc-status"><Sparkles size={13} /> 同学们在想这一页…</p>}
        {!busy && silence && <p className="nc-status">这次先听大家说。</p>}
        {!busy && !silence && !messages.length && <p className="nc-status">这一页还没有同学发言。</p>}
        {messages.map((message, index) => {
          const person = byId.get(message.agentId);
          return <div key={`${message.agentId}-${index}`} className="nc-bubble">
            <span className="nc-bubble__name">{person?.name || message.agentId}</span>
            <p>{message.text}</p>
          </div>;
        })}
        {error && <div className="nc-error" role="alert">
          <p>{error}</p>
          {!exhausted && <button type="button" onClick={retry}>重试</button>}
        </div>}
      </div>

      <form className="nc-ask" onSubmit={submit}>
        <label>
          <span className="sr-only">点名提问</span>
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={selected ? `问 ${byId.get(selected)?.name || "同学"} 一个问题…` : "先点一位同学再提问"}
            maxLength={600}
            disabled={!selected || exhausted || asking}
          />
        </label>
        <button type="submit" disabled={!selected || !draft.trim() || asking || exhausted} aria-label="发送提问">
          <Send size={14} />
        </button>
      </form>
      <p className="nc-hint"><MessageCircle size={12} /> 只有被问到的同学会回答；测验页不会直接给答案。</p>
    </aside>}
  </div>;
}

function comboLabel(left, budget) {
  if (!budget) return null;
  const percent = Math.round((left / budget) * 100);
  return <span className="nc-budget">{percent}%</span>;
}
