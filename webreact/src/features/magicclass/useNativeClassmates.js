import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { askClassmate, getClassmateBudget, getClassmateRoster, respondClassmates } from "../../data/classmateApi.js";
import {
  addLines,
  addPage,
  budgetLeft,
  bumpUsage,
  memoryKey,
  memoryPayload,
  readMemory,
  writeMemory,
} from "./classmateMemory.js";

/**
 * 测验答案字段绝不能进同学上下文。
 *
 * 同学发言是“和同学一起看这一页”，不是提前拿到答案；如果把这些字段一起
 * 抽成纯文本，模型完全可能在被点名时把正确选项说出来。这里按字段名剔除，
 * 只留下题干、选项和学习目标。
 */
const CLASSMATE_SPOILER_FIELDS = new Set([
  "answer",
  "answers",
  "correct",
  "correctAnswer",
  "correctAnswers",
  "acceptedAnswer",
  "acceptedAnswers",
  "analysis",
  "explanation",
  "solution",
  "hint",
  "hints",
  "commentPrompt",
]);

function collectText(value, parts, depth = 0) {
  if (parts.length >= 60 || depth > 6) return;
  if (typeof value === "string") {
    const text = value.trim();
    if (text) parts.push(text);
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item) => collectText(item, parts, depth + 1));
    return;
  }
  if (value && typeof value === "object") {
    Object.entries(value).forEach(([key, item]) => {
      if (CLASSMATE_SPOILER_FIELDS.has(key)) return;
      collectText(item, parts, depth + 1);
    });
  }
}

export function scenePayloadOf(scene, outline, sceneId) {
  if (!scene || !sceneId) return null;
  const type = scene?.content?.type || outline?.type;
  if (!type) return null;
  // 只把正文抽成纯文本，避免把整块画布/媒体塞进 40 KB 上限；类型必须与页面一致。
  const parts = [];
  collectText(scene.content, parts);
  return {
    id: sceneId,
    title: outline?.title || "课堂内容",
    type,
    content: { type, text: parts.join("\n").slice(0, 20_000) },
    actions: [],
  };
}

/**
 * 原生课堂的同学发言与点名。
 *
 * 只做浏览器该做的事：攒记忆、扣预算、决定何时请求。谁开口、说不说话由
 * 服务端路由决定；请求失败或预算用尽时**不编台词**，如实显示状态。
 */
export function useNativeClassmates({ courseId, stageId, scene, outline, sceneId, ready = false }) {
  const storage = typeof window !== "undefined" ? window.localStorage : null;
  const key = useMemo(() => memoryKey(stageId), [stageId]);
  const [memory, setMemory] = useState(() => readMemory(storage, key));
  const memoryRef = useRef(memory);
  const [roster, setRoster] = useState([]);
  const [budget, setBudget] = useState(240_000);
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [silence, setSilence] = useState(false);
  const [asking, setAsking] = useState(false);
  const [asked, setAsked] = useState(null);
  const [retryTick, setRetryTick] = useState(0);
  const inFlightScene = useRef("");
  const sceneRef = useRef(scenePayloadOf(scene, outline, sceneId));

  sceneRef.current = scenePayloadOf(scene, outline, sceneId);

  const commit = useCallback((next) => {
    memoryRef.current = next;
    setMemory(next);
    writeMemory(storage, key, next);
  }, [key, storage]);

  useEffect(() => {
    const loaded = readMemory(storage, key);
    memoryRef.current = loaded;
    setMemory(loaded);
    setMessages([]);
    setError("");
    setSilence(false);
    setAsked(null);
    inFlightScene.current = "";
  }, [key, storage]);

  useEffect(() => {
    let alive = true;
    Promise.all([
      getClassmateRoster().catch(() => ({ items: [] })),
      getClassmateBudget().catch(() => null),
    ]).then(([rosterPayload, budgetPayload]) => {
      if (!alive) return;
      setRoster(Array.isArray(rosterPayload?.items) ? rosterPayload.items : []);
      if (budgetPayload && Number(budgetPayload.token_budget) > 0) {
        setBudget(Number(budgetPayload.token_budget));
      }
    });
    return () => { alive = false; };
  }, []);

  // 换页自动发言。同一页只请求一次；预算用尽时不再请求。
  useEffect(() => {
    const payload = ready ? sceneRef.current : null;
    if (!payload || !courseId) return;
    if (inFlightScene.current === payload.id) return;
    if (budgetLeft(memoryRef.current, budget) <= 0) {
      setSilence(true);
      setMessages([]);
      return;
    }
    inFlightScene.current = payload.id;
    let alive = true;
    setBusy(true);
    setError("");
    setSilence(false);
    setMessages([]);
    respondClassmates({
      courseId,
      scene: payload,
      memory: memoryPayload(memoryRef.current),
    }).then((result) => {
      if (!alive) return;
      const incoming = Array.isArray(result?.messages) ? result.messages : [];
      setMessages(incoming);
      setSilence(incoming.length === 0);
      let next = addPage(memoryRef.current, payload.title);
      next = addLines(next, incoming);
      next = bumpUsage(next, result?.usage?.tokens);
      commit(next);
    }).catch((failure) => {
      if (!alive) return;
      setError(failure?.response?.data?.message || failure?.message || "同学发言生成失败");
    }).finally(() => {
      if (alive) setBusy(false);
    });
    return () => { alive = false; };
  }, [courseId, sceneId, budget, commit, key, ready, retryTick]);

  const retry = useCallback(() => {
    inFlightScene.current = "";
    setError("");
    setRetryTick((value) => value + 1);
  }, []);

  const ask = useCallback(async (agentId, question) => {
    const payload = sceneRef.current;
    const trimmed = String(question || "").trim();
    if (!payload || !agentId || !trimmed || asking) return;
    const left = budgetLeft(memoryRef.current, budget);
    if (left <= 0) {
      setError("这节课的同学额度已用完，先自己读完这一页吧。");
      return;
    }
    setAsking(true);
    setError("");
    try {
      const result = await askClassmate({
        courseId,
        scene: payload,
        memory: memoryPayload(memoryRef.current),
        agentId,
        question: trimmed.slice(0, 600),
      });
      const message = result?.message;
      if (message?.text) {
        setMessages((current) => [...current, message]);
        setAsked({ agentId: message.agentId, question: trimmed });
        let next = addLines(memoryRef.current, [message]);
        next = bumpUsage(next, result?.usage?.tokens);
        commit(next);
      }
    } catch (failure) {
      setError(failure?.response?.data?.message || failure?.message || "同学暂时回答不了，请稍后再问。");
    } finally {
      setAsking(false);
    }
  }, [asking, budget, commit, courseId]);

  return {
    roster,
    messages,
    memory,
    busy,
    error,
    silence,
    asking,
    asked,
    budget,
    left: budgetLeft(memory, budget),
    ask,
    retry,
  };
}
