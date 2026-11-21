import React from "react";
import { Eraser, Save, X } from "lucide-react";

import { MagicClassSlideSurface } from "../../magicclass/slide/index.js";
import { addWhiteboardText, clearWhiteboard, cloneBoard } from "../../features/magicclass/whiteboardModel.js";
import "../../styles/magicclass-whiteboard.css";

export default function NativeWhiteboard({ board, revision, title, onSave, onClose }) {
  const [current, setCurrent] = React.useState(() => cloneBoard(board));
  const [draft, setDraft] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");
  const [notice, setNotice] = React.useState("");

  React.useEffect(() => {
    setCurrent(cloneBoard(board));
    setDraft("");
    setError("");
    setNotice("");
  }, [board]);

  const dirty = JSON.stringify(current.elements) !== JSON.stringify(board.elements);

  const addText = (event) => {
    event.preventDefault();
    try {
      const id = globalThis.crypto?.randomUUID?.() || `wb-text-${Date.now()}`;
      setCurrent(addWhiteboardText(current, draft, id));
      setDraft("");
      setError("");
      setNotice("文字卡已加入，保存后写入课堂。");
    } catch (failure) {
      setError(failure.message || "无法添加文字卡");
    }
  };

  const removeAll = () => {
    if (!current.elements.length) return;
    try {
      setCurrent(clearWhiteboard(current));
      setError("");
      setNotice("已清空白板，保存后生效。");
    } catch (failure) {
      setError(failure.message || "无法清空白板");
    }
  };

  const save = async () => {
    if (busy) return;
    if (!Number.isFinite(Number(revision))) {
      setError("当前舞台没有 revision，无法安全保存白板。");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await onSave(cloneBoard(current));
      if (result?.board) setCurrent(cloneBoard(result.board));
      setNotice("白板已保存到当前舞台。");
    } catch (failure) {
      setError(failure?.message || "白板保存失败");
    } finally {
      setBusy(false);
    }
  };

  const width = current.viewportSize || 1000;
  const height = width * (current.viewportRatio || 9 / 16);
  const canvas = {
    ...current,
    width,
    height,
    background: current.background || { type: "solid", color: "#F7F3E8" },
    elements: current.elements,
  };

  return <div className="wb-overlay" role="dialog" aria-modal="true" aria-label="课堂白板">
    <div className="wb-panel">
      <header className="wb-head">
        <div>
          <span className="wb-eyebrow">STUDY BOARD</span>
          <strong>{title || "课堂白板"}</strong>
          <small>{current.elements.length} 个元素 · 保存后写入舞台</small>
        </div>
        <button type="button" className="wb-icon" onClick={onClose} aria-label="关闭白板"><X size={16} /></button>
      </header>

      <div className="wb-stage" aria-label="白板画布">
        <MagicClassSlideSurface
          canvas={canvas}
          sceneId={`whiteboard-${current.id}`}
          effectsEnabled={false}
          elementIdPrefix="whiteboard-"
        />
      </div>
      <p className="wb-mobile-hint">左右滑动可查看整块板书</p>

      <form className="wb-tools" onSubmit={addText}>
        <label className="wb-input">
          <span className="sr-only">白板文字</span>
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="写一条板书，例如：左右极限必须相等"
            maxLength={600}
            disabled={busy}
          />
        </label>
        <button type="submit" className="wb-primary" disabled={busy || !draft.trim()}>加入板书</button>
        <button type="button" className="wb-quiet" onClick={removeAll} disabled={busy || !current.elements.length}>
          <Eraser size={14} /> 清空
        </button>
        <button type="button" className="wb-save" onClick={save} disabled={busy || !dirty}>
          <Save size={14} /> {busy ? "保存中…" : dirty ? "保存白板" : "已保存"}
        </button>
      </form>

      {error ? <p className="wb-error" role="alert">{error}</p> : null}
      {notice ? <p className="wb-notice" role="status">{notice}</p> : null}
      <p className="wb-hint">白板是这节课的共享板书；保存时会带上当前 revision，避免覆盖别人刚做的修改。</p>
    </div>
  </div>;
}
