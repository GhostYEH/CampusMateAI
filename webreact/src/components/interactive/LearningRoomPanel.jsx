import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Modal } from "../Primitives.jsx";
import {
  acceptLearningInvitation, createLearningRoom, declineLearningInvitation,
  findLearningStudent, getLearningArchive, getLearningIdentity, getLearningMessages,
  getLearningRoom, getLearningSupervision, inviteLearningStudent, leaveLearningRoom,
  listLearningInvitations, listLearningRooms, reportLearningAttention, sendLearningMessage,
  sendLearningNudge, setLearningCursor,
} from "../../data/learningRoomApi.js";
import {
  attentionLabel, attentionSignal, HIDDEN_AWAY_AFTER_MS, mergeSupervisionNudge, pickFreshNudge,
} from "../../data/learningRoomSupervision.js";
import { isLearningRoomMessage, LEARNING_ROOM_CHANNEL, mergeLearningMessages } from "../../data/learningRoomBridge.js";

const errorText = (error) => error?.response?.data?.message || error?.response?.data?.detail || error?.message || "操作失败，请重试";

export default function LearningRoomPanel({ origin, iframeRef }) {
  const [identity, setIdentity] = useState(null);
  const [invitations, setInvitations] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [active, setActive] = useState(null);
  const [frameState, setFrameState] = useState(null);
  const [entry, setEntry] = useState(null);
  const [uid, setUid] = useState("");
  const [queued, setQueued] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [bridgeReady, setBridgeReady] = useState(false);
  const [follow, setFollow] = useState(true);
  const [supervision, setSupervision] = useState(null);
  const [attentionEnabled, setAttentionEnabled] = useState(true);
  const [attentionState, setAttentionState] = useState("UNKNOWN");
  const [teacherNudge, setTeacherNudge] = useState(null);
  const requests = useRef(new Map());
  const activeRef = useRef(null);
  const roomEpoch = useRef(0);
  const messageCursor = useRef(0);
  const sharing = useRef(false);
  const alive = useRef(true);
  const lastCursor = useRef(-1);
  const cursorWrites = useRef({ running: false, pending: null });
  const messageAttempt = useRef(null);
  const chatEnd = useRef(null);
  const lastNudgeId = useRef(0);
  const nudgesInitialized = useRef(false);
  const lastSpokenNudgeId = useRef(0);
  const lastInteraction = useRef(Date.now());
  const hiddenSince = useRef(null);
  const identityRef = useRef(null);

  const post = useCallback((type, data = {}) => {
    iframeRef.current?.contentWindow?.postMessage({ channel: LEARNING_ROOM_CHANNEL, type, ...data }, origin);
  }, [origin, iframeRef]);

  const request = useCallback((type, data) => new Promise((resolve, reject) => {
    const requestId = crypto.randomUUID();
    const timer = setTimeout(() => {
      requests.current.delete(requestId);
      reject(new Error("课堂准备超时，请重试"));
    }, 120000);
    requests.current.set(requestId, { resolve, reject, timer });
    post(type, { ...data, requestId });
  }), [post]);

  const selectRoom = useCallback((value) => {
    roomEpoch.current += 1;
    activeRef.current = value;
    messageCursor.current = 0;
    lastCursor.current = -1;
    lastNudgeId.current = 0;
    nudgesInitialized.current = false;
    hiddenSince.current = null;
    setMessages([]);
    setSupervision(null);
    setAttentionState("UNKNOWN");
    setTeacherNudge(null);
    setActive(value);
  }, []);

  useEffect(() => {
    alive.current = true;
    const pendingRequests = requests.current;
    const receive = (event) => {
      if (!isLearningRoomMessage(event, origin, iframeRef.current?.contentWindow)) return;
      const data = event.data;
      if (data.type === "ready") setBridgeReady(true);
      if (data.type === "entry" && typeof data.stageId === "string" && typeof data.requestId === "string") {
        setEntry(data);
        setUid("");
        setNotice("");
      }
      if (data.type === "state") setFrameState(data);
      if (data.type === "result") {
        const pending = pendingRequests.get(data.requestId);
        if (!pending) return;
        clearTimeout(pending.timer);
        pendingRequests.delete(data.requestId);
        if (data.error) pending.reject(new Error(data.error));
        else pending.resolve(data);
      }
    };
    window.addEventListener("message", receive);
    getLearningIdentity().then((value) => { if (alive.current) { identityRef.current = value; setIdentity(value); } })
      .catch((error) => { if (alive.current) setNotice(errorText(error)); });
    return () => {
      alive.current = false;
      window.removeEventListener("message", receive);
      pendingRequests.forEach(({ reject, timer }) => { clearTimeout(timer); reject(new Error("已离开学习空间")); });
      pendingRequests.clear();
    };
  }, [origin, iframeRef]);

  const perform = async (action) => {
    setBusy(true);
    setNotice("");
    try { await action(); }
    catch (error) { if (alive.current) setNotice(errorText(error)); }
    finally { if (alive.current) setBusy(false); }
  };

  const speakNudge = useCallback((nudge) => {
    if (!nudge || nudge.id <= lastSpokenNudgeId.current ||
      typeof window === "undefined" || !("speechSynthesis" in window)) return;
    lastSpokenNudgeId.current = nudge.id;
    try {
      window.speechSynthesis.cancel();
      const utterance = new window.SpeechSynthesisUtterance(nudge.content);
      utterance.lang = "zh-CN";
      utterance.rate = 0.98;
      window.speechSynthesis.speak(utterance);
    } catch {
      // 浏览器可能要求用户手势后才允许语音；文字提醒仍然可见。
    }
  }, []);

  // 浏览器端监督只上报页面可见性与交互间隔，不打开摄像头。
  useEffect(() => {
    if (!active?.room?.id || !attentionEnabled) return undefined;
    let current = true;
    const report = async () => {
      const roomId = activeRef.current?.room?.id;
      if (!roomId || !alive.current) return;
      const now = Date.now();
      const hidden = document.visibilityState === "hidden";
      if (hidden && hiddenSince.current == null) hiddenSince.current = now;
      if (!hidden) hiddenSince.current = null;
      const state = attentionSignal({
        hidden,
        hiddenForMs: hidden ? now - hiddenSince.current : 0,
        idleForMs: now - lastInteraction.current,
      });
      try {
        const result = await reportLearningAttention(roomId, state, "PAGE_VISIBILITY");
        if (!current || !alive.current) return;
        setAttentionState(result.state);
        if (result.teacher_reminder) {
          setTeacherNudge((old) => mergeSupervisionNudge(old, result.teacher_reminder));
          speakNudge(result.teacher_reminder);
        }
      } catch {
        // 网络或课堂已结束时保持本地状态，不打断学习。
      }
    };
    let hiddenTimer;
    const interact = () => { lastInteraction.current = Date.now(); };
    const visibility = () => {
      window.clearTimeout(hiddenTimer);
      if (document.visibilityState === "hidden") {
        hiddenSince.current = Date.now();
        report();
        hiddenTimer = window.setTimeout(report, HIDDEN_AWAY_AFTER_MS + 1_000);
      } else {
        hiddenSince.current = null;
        report();
      }
    };
    report();
    const timer = window.setInterval(report, 20_000);
    window.addEventListener("pointerdown", interact, true);
    window.addEventListener("keydown", interact, true);
    window.addEventListener("scroll", interact, true);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      current = false;
      window.clearInterval(timer);
      window.clearTimeout(hiddenTimer);
      window.removeEventListener("pointerdown", interact, true);
      window.removeEventListener("keydown", interact, true);
      window.removeEventListener("scroll", interact, true);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, [active?.room?.id, attentionEnabled, speakNudge]);

  // A bounded, non-overlapping poll keeps invitation and chat state usable across devices.
  useEffect(() => {
    let current = true;
    let timer;
    const poll = async () => {
      let selected = null;
      let selectedEpoch = roomEpoch.current;
      try {
        const [inviteResult, roomResult] = await Promise.all([listLearningInvitations(), listLearningRooms()]);
        if (!current) return;
        setInvitations(inviteResult.items);
        setRooms(roomResult.items);
        selected = activeRef.current;
        selectedEpoch = roomEpoch.current;
        if (selected) {
          const [room, chat] = await Promise.all([getLearningRoom(selected.room.id), getLearningMessages(selected.room.id, messageCursor.current)]);
          if (!current || roomEpoch.current !== selectedEpoch || activeRef.current?.room.id !== room.id) return;
          const next = { ...activeRef.current, room };
          activeRef.current = next;
          setActive(next);
          if (chat.items.length) {
            messageCursor.current = chat.items.at(-1).id;
            setMessages((old) => mergeLearningMessages(old, chat.items));
          }
          const sup = await getLearningSupervision(room.id, lastNudgeId.current);
          if (!current || roomEpoch.current !== selectedEpoch || activeRef.current?.room.id !== room.id) return;
          const fresh = pickFreshNudge({
            nudges: sup.nudges,
            after: lastNudgeId.current,
            meUid: sup.me?.uid || identityRef.current?.uid,
            initialized: nudgesInitialized.current,
          });
          if (!nudgesInitialized.current) {
            nudgesInitialized.current = true;
            lastNudgeId.current = fresh.newest;
          } else {
            if (fresh.newest > lastNudgeId.current) lastNudgeId.current = fresh.newest;
            if (fresh.nudge) {
              setTeacherNudge((old) => mergeSupervisionNudge(old, fresh.nudge));
              speakNudge(fresh.nudge);
            }
          }
          setSupervision(sup);
          setAttentionState(sup.me?.state || "UNKNOWN");
        }
      } catch (error) {
        if (!current) return;
        if (selected && roomEpoch.current !== selectedEpoch) return;
        setNotice(errorText(error));
        if (selected && activeRef.current?.room.id === selected.room.id &&
            [404, 410].includes(error?.response?.status)) selectRoom(null);
      } finally {
        if (current) timer = setTimeout(poll, 2000);
      }
    };
    poll();
    return () => { current = false; clearTimeout(timer); };
  }, [selectRoom, speakNudge]);

  useEffect(() => { chatEnd.current?.scrollIntoView({ block: "nearest" }); }, [messages]);

  // New generation enters with its first page; invitations wait for the complete deck.
  useEffect(() => {
    if (!queued || !frameState?.complete || frameState.stageId !== queued.stageId || sharing.current) return;
    sharing.current = true;
    setBusy(true);
    let createdRoom = null;
    (async () => {
      try {
        const snapshot = await request("export", { stageId: queued.stageId });
        if (!alive.current) return;
        createdRoom = await createLearningRoom(snapshot);
        await inviteLearningStudent(createdRoom.id, queued.uid);
        if (!alive.current) return;
        selectRoom({ room: createdRoom, localStageId: snapshot.stageId });
        setQueued(null);
        setNotice("邀请已发送，等待同学接受。课件翻页将同步给跟随课堂的同学。");
      } catch (error) {
        if (createdRoom) await leaveLearningRoom(createdRoom.id).catch(() => {});
        if (alive.current) { setNotice(errorText(error)); setQueued(null); }
      } finally {
        sharing.current = false;
        if (alive.current) setBusy(false);
      }
    })();
  }, [queued, frameState, request, selectRoom]);

  useEffect(() => {
    if (!active || !frameState?.complete || frameState.stageId !== active.localStageId) return;
    if (active.room.host_uid === identity?.uid) {
      if (lastCursor.current === frameState.sceneIndex) return;
      lastCursor.current = frameState.sceneIndex;
      const writes = cursorWrites.current;
      writes.pending = { roomId: active.room.id, index: frameState.sceneIndex };
      if (writes.running) return;
      writes.running = true;
      (async () => {
        try {
          while (writes.pending && alive.current) {
            const next = writes.pending;
            writes.pending = null;
            if (activeRef.current?.room.id !== next.roomId) continue;
            try { await setLearningCursor(next.roomId, next.index); }
            catch (error) {
              if (alive.current && activeRef.current?.room.id === next.roomId) {
                lastCursor.current = -1;
                setNotice(errorText(error));
              }
            }
          }
        } finally { writes.running = false; }
      })();
    } else if (follow) {
      post("cursor", { stageId: active.localStageId, sceneIndex: active.room.scene_index });
    }
  }, [active, frameState, identity, follow, post]);

  const closeEntry = () => {
    if (busy) return;
    post("cancel", { requestId: entry.requestId });
    setEntry(null);
  };

  const enter = (invite) => perform(async () => {
    if (invite) {
      const student = await findLearningStudent(uid);
      setQueued({ uid: student.uid, stageId: entry.stageId });
      setNotice("正在准备共同课堂，课件生成完成后会自动发送邀请。");
    } else setQueued(null);
    selectRoom(null);
    post("enter", { requestId: entry.requestId });
    setEntry(null);
  });

  const join = (roomId, accept = false) => perform(async () => {
    if (!bridgeReady) throw new Error("正在连接课堂，请稍后重试");
    const room = accept ? await acceptLearningInvitation(roomId) : await getLearningRoom(roomId);
    const archive = await getLearningArchive(roomId);
    const imported = await request("import", { archive, sceneIndex: room.scene_index });
    if (alive.current) {
      selectRoom({ room, localStageId: imported.stageId });
      setQueued(null);
      setNotice("已加入同一课堂，可以在这里和同学交流。");
    }
  });

  const send = (event) => {
    event.preventDefault();
    const content = draft.trim();
    if (!content || busy || !active) return;
    perform(async () => {
      if (messageAttempt.current?.content !== content) messageAttempt.current = { content, id: crypto.randomUUID() };
      await sendLearningMessage(active.room.id, content, messageAttempt.current.id);
      if (alive.current) { setDraft(""); messageAttempt.current = null; }
    });
  };

  return (
    <aside className="learning-room-panel" aria-label="同学一起学" aria-busy={!bridgeReady}>
      <h2>同学一起学</h2>
      <div className="learning-room-identity">
        <span>我的 UID</span><code>{identity?.uid || "正在读取…"}</code>
        <Button variant="quiet" disabled={!identity} onClick={() => perform(async () => {
          await navigator.clipboard.writeText(identity.uid);
          setNotice("UID 已复制，可发给同学。");
        })}>复制 UID</Button>
      </div>
      {notice && <p className="learning-room-notice" role="status">{String(notice)}</p>}
      {queued && <p>{frameState?.mediaFailed ? "课堂图片或视频生成失败，请在课堂重试；完成后会继续发送邀请。" : "正在准备课件，完成后邀请同学加入。"}<Button variant="quiet" disabled={busy} onClick={() => setQueued(null)}>取消邀请</Button></p>}
      {invitations.map((item) => (
        <article className="learning-room-invitation" key={item.room_id}>
          <strong>{item.host_name} 邀请你一起学</strong><p>{item.title}</p>
          <Button disabled={busy || !bridgeReady} onClick={() => join(item.room_id, true)}>接受并加入</Button>
          <Button variant="quiet" disabled={busy} onClick={() => perform(async () => {
            await declineLearningInvitation(item.room_id);
            setInvitations((old) => old.filter((invite) => invite.room_id !== item.room_id));
          })}>拒绝</Button>
        </article>
      ))}
      {!active && <p className="learning-room-hint">选择一门课堂，进入前输入同学 UID 邀请一起学习。也可以独自进入。</p>}
      {!active && !queued && frameState?.stageId && <form className="learning-room-invite-form" onSubmit={(event) => {
        event.preventDefault();
        perform(async () => {
          const student = await findLearningStudent(uid);
          setQueued({ uid: student.uid, stageId: frameState.stageId });
        });
      }}>
        <label htmlFor="learning-current-peer">邀请加入当前课堂</label>
        <input id="learning-current-peer" value={uid} maxLength={128} onChange={(event) => setUid(event.target.value)} placeholder="输入同学 UID" />
        <Button disabled={busy || !uid.trim()}>邀请一起学</Button>
      </form>}
      {!active && rooms.map((room) => <Button key={room.id} variant="secondary" disabled={busy || !bridgeReady} onClick={() => join(room.id)}>返回：{room.title}</Button>)}
      {active && <>
        <h3>{active.room.title}</h3>
        {teacherNudge && <article className="learning-room-nudge" role="status">
          <strong>{teacherNudge.kind === "TEACHER" ? "小伴老师提醒" : "老师提醒"}</strong>
          <p>{teacherNudge.content}</p>
          <Button variant="quiet" onClick={() => setTeacherNudge(null)}>知道了</Button>
        </article>}
        <section className="learning-room-supervision">
          <div className="learning-room-supervision-head">
            <strong>课堂专注监督</strong>
            <Button variant="quiet" disabled={busy} onClick={() => setAttentionEnabled((value) => !value)}>
              {attentionEnabled ? "关闭观察" : "开启观察"}
            </Button>
          </div>
          <p className="learning-room-supervision-hint">浏览器按页面可见性和操作间隔辅助观察，不打开摄像头；只上报“专注/分心/离开”这类粗粒度状态。</p>
          <p>我的状态：{attentionLabel(attentionState)}{attentionEnabled ? "" : "（观察已关闭）"}</p>
          {active.room.host_uid === identity?.uid && supervision && <>
            {supervision.teacher_summary && <p className="learning-room-summary">{supervision.teacher_summary}</p>}
            {supervision.stats && <p className="learning-room-summary">在线 {supervision.stats.online}/{supervision.stats.total} · 专注 {supervision.stats.focused} · 需提醒 {supervision.stats.needs_attention}</p>}
            {supervision.members.filter((member) => !member.is_host).map((member) => (
              <div key={member.uid} className="learning-room-roster-row">
                <span><strong>{member.name || member.uid}</strong><em>{attentionLabel(member.state)} · {member.online ? "在线" : "状态超时"}</em></span>
                <Button variant="quiet" disabled={busy} onClick={() => perform(async () => {
                  await sendLearningNudge(active.room.id, member.uid);
                  setNotice(`已提醒 ${member.name || member.uid}。`);
                })}>提醒</Button>
              </div>
            ))}
            <Button variant="secondary" disabled={busy} onClick={() => perform(async () => {
              await sendLearningNudge(active.room.id, null);
              setNotice("已提醒全班。");
            })}>提醒全班</Button>
          </>}
          {active.room.host_uid !== identity?.uid && <p className="learning-room-supervision-hint">发起人只能看到粗粒度状态；老师提醒只发送给被提醒的同学。</p>}
        </section>
        <p className="learning-room-members">{active.room.members.map((member) => `${member.name}${member.status === "pending" ? "（待接受）" : ""}`).join("、")}</p>
        {frameState?.stageId !== active.localStageId && <Button disabled={busy} onClick={() => join(active.room.id)}>返回共同课堂</Button>}
        {active.room.host_uid !== identity?.uid && <label className="learning-room-follow"><input type="checkbox" checked={follow} onChange={(event) => setFollow(event.target.checked)} />跟随发起人翻页</label>}
        {active.room.host_uid === identity?.uid && <form className="learning-room-invite-form" onSubmit={(event) => {
          event.preventDefault();
          perform(async () => { await inviteLearningStudent(active.room.id, uid.trim()); setUid(""); setNotice("邀请已发送。"); });
        }}>
          <label htmlFor="learning-room-peer">邀请其他同学</label>
          <input id="learning-room-peer" value={uid} maxLength={128} onChange={(event) => setUid(event.target.value)} placeholder="输入同学 UID" />
          <Button disabled={busy || !uid.trim()}>发送邀请</Button>
        </form>}
        <div className="learning-room-messages" role="log" aria-label="课堂交流" aria-live="polite">
          {!messages.length && <p>一起讨论这门课吧。</p>}
          {messages.map((message) => <article key={message.id} className={message.uid === identity?.uid ? "is-self" : ""}><strong>{message.name}</strong><p>{message.content}</p></article>)}
          <div ref={chatEnd} />
        </div>
        <form onSubmit={send} className="learning-room-chat-form">
          <label htmlFor="learning-room-message">课堂消息</label>
          <textarea id="learning-room-message" value={draft} maxLength={2000} onChange={(event) => setDraft(event.target.value)} placeholder="和同学聊聊这门课…" />
          <Button disabled={busy || !draft.trim()}>发送</Button>
        </form>
        <Button variant="quiet" disabled={busy} onClick={() => perform(async () => {
          await leaveLearningRoom(active.room.id);
          selectRoom(null);
          post("home");
          setNotice("已离开共同课堂。");
        })}>{active.room.host_uid === identity?.uid ? "结束共同课堂" : "离开共同课堂"}</Button>
      </>}
      {entry && <Modal title="邀请同学一起进入课堂" onClose={closeEntry} actions={<>
        <Button variant="secondary" disabled={busy} onClick={() => enter(false)}>独自进入</Button>
        <Button disabled={busy || !uid.trim()} onClick={() => enter(true)}>邀请并进入</Button>
      </>}>
        <p>输入同学的 UID；对方接受邀请后会看到相同课件，并可与你文字交流。新课堂会等课件生成完成后发送邀请。</p>
        <label htmlFor="learning-entry-uid">同学 UID</label>
        <input id="learning-entry-uid" autoFocus value={uid} maxLength={128} onChange={(event) => setUid(event.target.value)} placeholder="例如 usr_…" />
        {notice && <p role="alert">{String(notice)}</p>}
      </Modal>}
    </aside>
  );
}
