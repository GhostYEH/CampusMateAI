import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../../data/api.js";
import { createPollScope } from "../../data/pollScope.js";
import { describeEntryFailure, resolveGenerationPhase, stageGenerationIdempotencyKey } from "./enterClassroomModel.js";
import { TOPIC_GENERATION_MODE } from "./homeGenerationModel.js";
import { workspaceHref } from "./quickAskModel.js";

export async function getGeneratedStageId(courseId, job) {
  if (!job?.artifact_id) throw new Error("任务已结束，但课堂产物暂不可读取。");
  const { blob } = await api.getMagicClassArtifact(courseId, job.artifact_id);
  const document = JSON.parse(await blob.text());
  const id = document?.stage?.id;
  if (typeof id !== "string" || !/^stg_[a-f0-9]{32}$/.test(id)) throw new Error("课堂产物缺少有效标识。");
  return id;
}

export function useTopicClassroomGeneration(courseId) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [phase, setPhase] = useState(null);
  const scopeRef = useRef(null);
  if (!scopeRef.current) scopeRef.current = createPollScope();
  const scope = scopeRef.current;
  const cancelWait = useRef(null);

  useEffect(() => () => {
    cancelWait.current?.();
    cancelWait.current = null;
    scope.stop();
  }, [scope]);

  async function openCompleted(workspaceId, job, token) {
    const stageId = job.mode === TOPIC_GENERATION_MODE ? await getGeneratedStageId(courseId, job) : "";
    if (scope.isCurrent(token)) navigate(workspaceHref(courseId, workspaceId, "", { mode: "playback", stageId }), { replace: true });
  }

  async function waitForJob(jobId, workspaceId, token) {
    // Two model attempts can each use the configured two-minute timeout.
    for (let attempt = 0; attempt < 375; attempt += 1) {
      if (!scope.isCurrent(token)) return;
      const job = await api.getMagicClassJob(courseId, jobId);
      if (!scope.isCurrent(token)) return;
      setPhase(resolveGenerationPhase(job));
      if (job.status === "completed") { await openCompleted(workspaceId, job, token); return; }
      if (["failed", "cancelled"].includes(job.status)) throw { response: { status: 200, data: job } };
      const shouldContinue = await new Promise((resolve) => {
        cancelWait.current = () => resolve(false);
        scope.arm(() => {
          cancelWait.current = null;
          scope.disarm();
          resolve(true);
        }, 800, token);
      });
      if (!shouldContinue) return;
    }
    throw new Error("课堂仍在生成，稍后再次提交同一主题可继续查看进度。");
  }

  async function generate(value) {
    const topic = value.trim();
    if (!topic || !courseId || busy) return;
    cancelWait.current?.();
    cancelWait.current = null;
    scope.stop();
    const token = scope.begin();
    setBusy(true);
    setError("");
    setPhase(null);
    try {
      const result = await api.generateMagicClassHome(courseId, {
        mode: TOPIC_GENERATION_MODE, prompt: topic, idempotencyKey: stageGenerationIdempotencyKey(courseId, topic),
      });
      if (!scope.isCurrent(token)) return;
      const workspaceId = result?.workspace_id;
      if (!workspaceId) throw new Error("网关未返回课程工作台");
      const job = result?.job;
      if (!job?.id) throw new Error("受管服务未返回生成任务");
      if (job.status === "completed") {
        await openCompleted(workspaceId, job, token);
      } else {
        if (["failed", "cancelled"].includes(job.status)) await api.retryMagicClassJob(courseId, job.id);
        if (scope.isCurrent(token)) await waitForJob(job.id, workspaceId, token);
      }
    } catch (cause) {
      if (scope.isCurrent(token)) setError(cause?.response ? describeEntryFailure(cause).message : cause?.message || "课堂生成失败，请重试。");
    } finally {
      if (scope.isCurrent(token)) setBusy(false);
    }
  }

  return { generate, busy, error, phase };
}
