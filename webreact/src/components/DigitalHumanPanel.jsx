import { memo, useEffect, useRef } from "react";
import { Icon } from "./Icon.jsx";

function DigitalHumanPanel({ speaking, muted, status, canReplay, onReady, onError, onToggleMuted, onStop, onReplay }) {
  const frameRef = useRef(null);
  useEffect(() => {
    const handleUnityMessage = (event) => {
      if (event.origin !== window.location.origin || event.data?.source !== "campusmate-unity") return;
      if (event.data.type === "ready") onReady(frameRef.current);
      if (event.data.type === "error") onError();
    };
    window.addEventListener("message", handleUnityMessage);
    return () => window.removeEventListener("message", handleUnityMessage);
  }, [onError, onReady]);
  const stateLabel = speaking ? "正在讲解" : status === "ready" ? "随时为你解答" : status === "error" ? "静态模式" : "正在载入";
  return <section className={`counselor-panel digital-human-card counselor-digital-human ${speaking ? "speaking" : ""}`} aria-labelledby="digital-human-title">
    <header className="digital-human-header"><div><span className="digital-human-kicker">你的学习小帮手</span><h2 id="digital-human-title">CampusMate 数字人</h2></div><span className="digital-human-state" role="status"><i aria-hidden="true" />{stateLabel}</span></header>
    <div className="digital-human-stage" aria-busy={status === "loading"}>
      {status !== "error" && <iframe ref={frameRef} className="digital-human-frame" src="/digital-human/index.html" title="CampusMate AI 数字人" allow="autoplay" onLoad={() => onReady(frameRef.current)} onError={onError} />}
      {status === "loading" && <div className="digital-human-loading" role="status"><span aria-hidden="true" />正在唤醒数字人…</div>}
      {status === "error" && <div className="digital-human-fallback"><img className="digital-human-fallback-avatar" src="/digital-human/fallback-avatar.png" alt="" /><img src="/assets/campusmate-counselor-hero.png" alt="CampusMate AI 助手" /><p>数字人画面暂未加载，文字与语音功能仍可使用。</p></div>}
    </div>
    <footer className="digital-human-controls"><button type="button" aria-pressed={muted} onClick={onToggleMuted}><Icon name={muted ? "PhSpeakerSlash" : "PhSpeakerHigh"} size={16} />{muted ? "开启语音" : "静音"}</button><button type="button" disabled={!speaking} onClick={onStop}><Icon name="PhStop" size={16} />停止</button><button type="button" disabled={!canReplay || speaking || muted} onClick={onReplay}><Icon name="PhArrowCounterClockwise" size={16} />重播</button></footer>
  </section>;
}

export default memo(DigitalHumanPanel);
