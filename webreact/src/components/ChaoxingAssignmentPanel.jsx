import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../data/api.js";
import { assignmentHasEnded, assignmentReviewError as errorText } from "../features/magicclass/assignmentReviewModel.js";
import { Button, Panel, SectionHeading } from "./Primitives.jsx";

export default function ChaoxingAssignmentPanel({ task, onSynced }) {
  const navigate = useNavigate();
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [review, setReview] = useState(null);
  const alive = useRef(false);
  const pending = useRef(false);

  useEffect(() => {
    alive.current = true;
    let current = true;
    setLoading(true);
    api.getChaoxingAssignmentContent(task.id).then((result) => {
      if (current) setContent(result);
    }).catch((failure) => {
      if (current) setError(errorText(failure));
    }).finally(() => { if (current) setLoading(false); });
    return () => { current = false; alive.current = false; };
  }, [task.id, task.status, task.deadline]);

  useEffect(() => {
    if (!review?.job?.id || !["queued", "running"].includes(review.job.status)) return undefined;
    let current = true;
    const timer = window.setTimeout(async () => {
      try {
        const job = await api.getMagicClassJob(review.course_id, review.job.id);
        if (current) setReview((previous) => ({ ...previous, job }));
      } catch (failure) { if (current) setError(errorText(failure)); }
    }, 2000);
    return () => { current = false; window.clearTimeout(timer); };
  }, [review]);

  async function sync() {
    if (pending.current) return;
    pending.current = true; setBusy("sync"); setError("");
    try {
      await api.syncChaoxing();
      if (alive.current) await onSynced();
      const result = await api.getChaoxingAssignmentContent(task.id);
      if (alive.current) setContent(result);
    } catch (failure) { if (alive.current) setError(errorText(failure)); }
    finally { pending.current = false; if (alive.current) setBusy(""); }
  }

  async function generate(scope = "all") {
    if (pending.current) return;
    pending.current = true;
    setBusy(scope === "wrong" ? "generate-wrong" : "generate");
    setError("");
    try {
      let result = await api.generateChaoxingAssignmentClassroom(task.id, { scope });
      if (["failed", "cancelled"].includes(result?.job?.status)) {
        const job = await api.retryMagicClassJob(result.course_id, result.job.id);
        result = { ...result, job };
      }
      if (alive.current) setReview(result);
    } catch (failure) { if (alive.current) setError(errorText(failure)); }
    finally { pending.current = false; if (alive.current) setBusy(""); }
  }

  const generating = ["queued", "running"].includes(review?.job?.status);
  const completed = review?.job?.status === "completed";
  const failed = ["failed", "cancelled"].includes(review?.job?.status);
  const failedScope = failed ? review?.scope || "all" : null;
  return <Panel>
    <SectionHeading title="作业自主练习与详解" detail={assignmentHasEnded(task) ? "作业已截止，可重做原题和变式练习" : "作业截止后开放复习；截止时间缺失时请先同步"} />
    <p className="muted-copy">由你选题、先练再看解析，卡住时逐步查看提示。全部题目复习会保留原题重做和变式；错题复习只出变式，不再出现原题。</p>
    {loading ? <p role="status">正在读取作业题目…</p> : content?.available ? <>
      <p className="muted-copy">已同步 {content.questions.length} 道题{!content.current && "，当前状态下的题目仍待更新"}。</p>
      {content.results_complete ? (
        content.wrong_count > 0
          ? <p className="muted-copy">已批改：错题 {content.wrong_count} 道。可以只生成错题变式讲解。</p>
          : <p className="muted-copy">已批改：本次作业全部正确，没有需要单独整理的错题。</p>
      ) : content.results_available ? (
        content.wrong_count > 0
          ? <p className="muted-copy">已取得部分批改结果：已批改 {content.graded_count}/{content.questions.length} 道，发现错题 {content.wrong_count} 道；其余题目尚未批改。</p>
          : <p className="muted-copy">已取得部分批改结果：已批改 {content.graded_count}/{content.questions.length} 道，暂未发现错题；其余题目尚未批改。</p>
      ) : <p className="muted-copy">尚未取得逐题批改结果，暂不能单独生成错题课；可以先按全部题目复习。</p>}
      <details><summary>查看同步的题干与选项</summary><ol>{content.questions.map((question) => <li key={question.number}><p className="rich-copy">{question.stem}</p>{question.options.length > 0 && <ul>{question.options.map((option, index) => <li key={index} className="rich-copy">{option}</li>)}</ul>}</li>)}</ol></details>
    </> : <p className="muted-copy">暂未取得题干与选项。点击同步重试；学习通登录过期时，请到个人中心重新连接。</p>}
    <div className="form-footer">
      <Button variant="secondary" disabled={Boolean(busy) || generating} onClick={sync}>{busy === "sync" ? "同步中…" : "同步作业与提交状态"}</Button>
      <Button icon="PhSparkle" disabled={loading || !content?.can_generate || Boolean(busy) || generating} onClick={() => generate("all")}>{busy === "generate" ? "正在创建课堂…" : failedScope === "all" ? "重试生成讲解与练习" : "生成作业讲解与练习"}</Button>
      {content?.can_generate_wrong && <Button variant="secondary" icon="PhTarget" disabled={Boolean(busy) || generating} onClick={() => generate("wrong")}>{busy === "generate-wrong" ? "正在生成错题课…" : failedScope === "wrong" ? "重试生成错题讲解" : "生成错题讲解（只出变式）"}</Button>}
    </div>
    {generating && <p role="status">课堂生成中：{review.job.progress || 0}% 。可以稍后回来，点击生成会继续查看同一任务。</p>}
    {failed && <p role="alert">本次课堂生成{review.job.status === "cancelled" ? "已取消" : "失败"}，可以重试。</p>}
    {completed && <Button onClick={() => navigate(`/courses/${review.course_id}/workspaces/${review.workspace_id}?mode=playback`)}>进入课堂学习</Button>}
    {error && <p className="page-notice notice-error" role="alert">{error}{generating && <button type="button" className="text-button" onClick={() => { setError(""); setReview((previous) => ({ ...previous })); }}>重新检查进度</button>}</p>}
  </Panel>;
}
