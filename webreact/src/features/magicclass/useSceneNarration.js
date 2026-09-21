import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "../../data/api.js";
import { describeNarrationFailure } from "./narrationModel.js";

/**
 * 一个场景的讲解音频。
 *
 * ## 为什么音频必须按 scene id 索引
 *
 * 之前 Web 端只有一条"输入文字 → 生成音频"的路径，音频和任何一页都没有关系，
 * 于是切页或刷新之后它就只能靠"最近生成的那个"来对应——那必然挂错页。
 * 现在每一页各自持有一份状态，键是场景 id：
 *
 * - 换页时**不共享**任何状态，A 页的音频不可能显示在 B 页上；
 * - 重新进入页面时用 `GET .../scenes/{sceneId}/narration` 反查服务端，
 *   所以刷新后关联关系由服务端给出，而不是靠前端记忆。
 *
 * ## 状态机
 *
 * `idle → checking → (none | ready | generating) → error`
 *
 * `none` 与 `error` 必须分开：前者是"这一页没有可讲解的文字"，后者是"合成失败，
 * 可以重试"。把两者合并成"没有音频"，学生就永远不知道该不该再点一次。
 */
export function useSceneNarration({ courseId, workspaceId, stageId, sceneId }) {
  const [state, setState] = useState("idle");
  const [hasScript, setHasScript] = useState(true);
  const [truncated, setTruncated] = useState(false);
  const [error, setError] = useState("");
  const [audioUrl, setAudioUrl] = useState("");
  const [notice, setNotice] = useState("");

  // 代次守卫：换场景或重复提交时，在飞任务的结果不得写进新上下文。
  const epoch = useRef(0);
  const objectUrl = useRef("");
  const timer = useRef(null);

  const releaseUrl = useCallback(() => {
    if (objectUrl.current && typeof URL !== "undefined") URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = "";
    setAudioUrl("");
  }, []);

  // 卸载或换场景时必须释放：不释放会泄漏 blob，而且旧音频在 B 页仍可播放。
  useEffect(() => () => {
    epoch.current += 1;
    if (timer.current) window.clearTimeout(timer.current);
    if (objectUrl.current && typeof URL !== "undefined") URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = "";
  }, [sceneId]);

  const loadArtifact = useCallback(async (artifactJob, mine) => {
    if (!artifactJob?.artifact_id) return;
    const artifact = await api.getMagicClassArtifact(courseId, artifactJob.artifact_id);
    if (mine !== epoch.current) return;
    // 后端只回受支持的类型；真遇到别的类型要如实说，而不是塞给 <audio> 变成静音。
    if (artifact.mediaType && !artifact.mediaType.includes("audio")) {
      setState("error");
      setError("讲解产物的类型不是音频，已停止播放。");
      return;
    }
    const next = URL.createObjectURL(artifact.blob);
    if (objectUrl.current && typeof URL !== "undefined") URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = next;
    setAudioUrl(next);
    setState("ready");
  }, [courseId]);

  const poll = useCallback(async (jobId, mine) => {
    const job = await api.getMagicClassJob(courseId, jobId);
    if (mine !== epoch.current) return;
    if (["queued", "running"].includes(job?.status)) {
      timer.current = window.setTimeout(() => { void poll(jobId, mine); }, 900);
      return;
    }
    if (job?.status !== "completed") {
      setState("error");
      setError(describeNarrationFailure({ code: job?.error_code }));
      return;
    }
    await loadArtifact(job, mine);
  }, [courseId, loadArtifact]);

  /** 读取这一页当前有没有音频。换场景、进页面都走它。 */
  const refresh = useCallback(async () => {
    if (!courseId || !workspaceId || !stageId || !sceneId) return;
    const mine = (epoch.current += 1);
    if (timer.current) window.clearTimeout(timer.current);
    releaseUrl();
    setError("");
    setNotice("");
    setState("checking");
    try {
      const status = await api.getMagicClassSceneNarration(courseId, workspaceId, stageId, sceneId);
      if (mine !== epoch.current) return;
      const scriptAvailable = status?.has_script !== false;
      setHasScript(scriptAvailable);
      setTruncated(Boolean(status?.truncated));
      const job = status?.job;
      if (!job) { setState(scriptAvailable ? "available" : "none"); return; }
      if (job.status === "completed" && job.artifact_id) { await loadArtifact(job, mine); return; }
      if (["queued", "running"].includes(job.status)) { setState("generating"); await poll(job.id, mine); return; }
      // 上一轮失败留下的任务：如实显示为可重试，而不是"没有音频"。
      setState("error");
      setError(describeNarrationFailure({ code: job.error_code }));
    } catch (failure) {
      if (mine !== epoch.current) return;
      // 读不到状态不等于"没有音频"，更不等于页面坏了：降级为可重试。
      setState("error");
      setError(describeNarrationFailure(failure));
    }
  }, [courseId, workspaceId, stageId, sceneId, loadArtifact, poll, releaseUrl]);

  useEffect(() => { void refresh(); }, [refresh]);

  /** 生成这一页的讲解。同一页重复点击由服务端三层去重复用同一任务。 */
  const generate = useCallback(async () => {
    if (!courseId || !workspaceId || !stageId || !sceneId) return;
    const mine = (epoch.current += 1);
    if (timer.current) window.clearTimeout(timer.current);
    releaseUrl();
    setError("");
    setNotice("");
    setState("generating");
    try {
      const result = await api.synthesizeMagicClassSceneNarration(courseId, workspaceId, stageId, sceneId, {
        idempotencyKey: api.newIdempotencyKey(),
      });
      if (mine !== epoch.current) return;
      if (result?.has_script === false) {
        setHasScript(false);
        setState("none");
        setNotice(result?.message || "这一页没有可讲解的文字。");
        return;
      }
      const job = result?.job;
      if (!job) { setState("error"); setError("受管服务未返回任务编号。"); return; }
      // 复用已有成品时服务端直接回 completed，不必轮询。
      if (job.status === "completed" && job.artifact_id) { await loadArtifact(job, mine); return; }
      if (["queued", "running"].includes(job.status)) { await poll(job.id, mine); return; }
      setState("error");
      setError(describeNarrationFailure({ code: job.error_code }));
    } catch (failure) {
      if (mine !== epoch.current) return;
      setState("error");
      setError(describeNarrationFailure(failure));
    }
  }, [courseId, workspaceId, stageId, sceneId, loadArtifact, poll, releaseUrl]);

  return {
    state, hasScript, truncated, error, notice, audioUrl,
    generating: state === "generating",
    checking: state === "checking" || state === "idle",
    ready: state === "ready" && Boolean(audioUrl),
    none: state === "none",
    failed: state === "error",
    generate,
    refresh,
  };
}
