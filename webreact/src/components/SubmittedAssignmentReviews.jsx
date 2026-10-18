import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import * as api from "../data/api.js";
import { useAsyncResource } from "../hooks/useAsyncResource.js";
import { assignmentReviewError, enterAssignmentReview, loadEndedAssignments } from "../features/magicclass/assignmentReviewModel.js";
import { formatDateTime } from "../utils/date.js";
import { Button } from "./Primitives.jsx";
import { Icon } from "./Icon.jsx";
import "../styles/assignment-reviews.css";

const phaseText = (phase) => ({ preparing: "正在准备讲解…", syncing: "正在同步作业题目…", retrying: "正在重试生成…", generating: `正在生成讲解 ${phase?.progress || 0}%` }[phase?.state] || "");

export default function SubmittedAssignmentReviews({ compact = false }) {
  const navigate = useNavigate();
  const resource = useAsyncResource(() => loadEndedAssignments(api.getTasks), []);
  const [visible, setVisible] = useState(6);
  const [active, setActive] = useState(null);
  const [error, setError] = useState("");
  const request = useRef(null);
  useEffect(() => () => { request.current?.abort(); request.current = null; }, []);

  async function enter(task) {
    if (request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setError(""); setActive({ taskId: task.id, state: "preparing" });
    try {
      const href = await enterAssignmentReview(task.id, api, {
        signal: controller.signal,
        onPhase: (phase) => { if (!controller.signal.aborted) setActive({ taskId: task.id, ...phase }); },
      });
      if (href && !controller.signal.aborted) navigate(href);
    } catch (failure) {
      if (!controller.signal.aborted) setError(assignmentReviewError(failure));
    } finally {
      if (request.current === controller) {
        request.current = null;
        if (!controller.signal.aborted) setActive(null);
      }
    }
  }

  const tasks = resource.data || [];
  return <section className={`assignment-reviews${compact ? " assignment-reviews--compact" : ""}`} aria-label="已截止作业">
    <header className="assignment-reviews__heading"><div><h2><Icon name="PhCheckSquare" size={19} />已截止作业</h2><p>先自己练，卡住再看提示和解析。</p></div><Button variant="secondary" disabled={resource.loading || Boolean(active)} onClick={() => { setError(""); void resource.reload(); }} aria-label="刷新已截止作业"><Icon name="PhArrowClockwise" size={16} /></Button></header>
    {resource.loading ? <p className="muted-copy" role="status">正在读取已截止作业…</p> : resource.error ? <p role="alert">作业列表读取失败，请点击刷新重试。</p> : tasks.length ? <>
      <ul className="assignment-reviews__list">{tasks.slice(0, visible).map((task) => <li key={task.id} className="assignment-reviews__card">
        <div className="assignment-reviews__copy"><strong>{task.title}</strong><small>{task.source_name || "学习通课程"} · {task.status === "completed" ? "已提交" : "未提交，可复习"}</small><small>截止时间：{formatDateTime(task.deadline, { dateStyle: "short", timeStyle: "short" })}</small></div>
        <div className="assignment-reviews__actions"><Button icon="PhPlay" disabled={Boolean(active) || !task.course_id} onClick={() => void enter(task)} aria-label={`进入《${task.title}》的练习课堂`}>{active?.taskId === task.id ? phaseText(active) : "进入练习与详解"}</Button><Link to={`/tasks/chaoxing/${encodeURIComponent(task.id)}`}>查看作业</Link></div>
        {!task.course_id && <small className="muted-copy">课程归属待同步，可先到作业详情同步。</small>}
      </li>)}</ul>
      {tasks.length > visible && <Button variant="secondary" onClick={() => setVisible((value) => value + 6)}>显示更多作业（还有 {tasks.length - visible} 份）</Button>}
    </> : <p className="muted-copy">暂无已截止的学习通作业。同步后会显示有明确截止时间的已结束作业。</p>}
    {active && <p role="status" className="assignment-reviews__status">{phaseText(active)}，完成后会自动进入课堂。</p>}
    {error && <p role="alert" className="assignment-reviews__error">{error}</p>}
  </section>;
}
