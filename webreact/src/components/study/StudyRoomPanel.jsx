import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Modal } from "../Primitives.jsx";
import * as roomApi from "../../data/studyRoomApi.js";

const POLL_MS = 5000;
const HEARTBEAT_MS = 15000;

const STATE_LABEL = { focus: "专注中", break: "休息中", away: "离开", idle: "待命" };
const STATE_TONE = { focus: "tone-green", break: "tone-orange", away: "tone-muted", idle: "tone-blue" };

function errText(error) {
  return error?.response?.data?.message || error?.response?.data?.detail || error?.message || "操作失败，请重试";
}

function mmss(totalSeconds) {
  const value = Math.max(0, Math.floor(totalSeconds));
  return `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
}

/**
 * 多人在线自习室面板：成员在线状态 + 共享番茄钟 + 房内鼓励。
 * 入口在「专注自习」页；纯轮询，无音视频。后端契约见 docs/api/05-study.md。
 */
export default function StudyRoomPanel({ open, onClose }) {
  const [identity, setIdentity] = useState(null);
  const [rooms, setRooms] = useState([]);
  const [invitations, setInvitations] = useState([]);
  const [room, setRoom] = useState(null);
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [uid, setUid] = useState("");
  const [title, setTitle] = useState("");
  const [draft, setDraft] = useState("");
  const [myState, setMyState] = useState("focus");
  const [statusMsg, setStatusMsg] = useState("");
  const [tick, setTick] = useState(0);
  const roomIdRef = useRef(null);
  const cursorRef = useRef(0);
  const detailAtRef = useRef(Date.now());
  const aliveRef = useRef(true);

  const currentRoomId = room?.id || null;
  roomIdRef.current = currentRoomId;

  const refreshLists = useCallback(async () => {
    try {
      const [me, roomList, invites] = await Promise.all([
        roomApi.getStudyRoomIdentity(),
        roomApi.listStudyRooms(),
        roomApi.listStudyRoomInvitations(),
      ]);
      if (!aliveRef.current) return;
      setIdentity(me);
      setRooms(roomList.items || []);
      setInvitations(invites.items || []);
    } catch (error) {
      if (aliveRef.current) setNotice(errText(error));
    }
  }, []);

  const loadRoom = useCallback(async (id) => {
    const detail = await roomApi.getStudyRoom(id);
    if (!aliveRef.current) return detail;
    detailAtRef.current = Date.now();
    setRoom(detail);
    const me = detail.members.find((m) => m.uid === (identity?.uid));
    if (me) setMyState(me.study_state);
    return detail;
  }, [identity?.uid]);

  const pullMessages = useCallback(async (id) => {
    let after = cursorRef.current;
    for (;;) {
      const page = await roomApi.getStudyRoomMessages(id, after);
      const items = page.items || [];
      if (!aliveRef.current) return;
      if (items.length) {
        cursorRef.current = items[items.length - 1].id;
        setMessages((prev) => roomApi.mergeStudyRoomMessages(prev, items));
      }
      if (items.length < 100) break;
      after = cursorRef.current;
    }
  }, []);

  // 打开面板：加载列表
  useEffect(() => {
    if (!open) return undefined;
    aliveRef.current = true;
    void refreshLists();
    return () => { aliveRef.current = false; };
  }, [open, refreshLists]);

  // 选中房间：轮询详情 + 消息，心跳，倒计时 tick
  useEffect(() => {
    if (!open || !currentRoomId) return undefined;
    let cancelled = false;
    const poll = async () => {
      try {
        await loadRoom(currentRoomId);
        await pullMessages(currentRoomId);
      } catch (error) {
        if (!cancelled) setNotice(errText(error));
      }
    };
    cursorRef.current = 0;
    detailAtRef.current = Date.now();
    void poll();
    const pollTimer = setInterval(poll, POLL_MS);
    const beatTimer = setInterval(() => { roomApi.heartbeatStudyRoom(currentRoomId).catch(() => {}); }, HEARTBEAT_MS);
    const tickTimer = setInterval(() => setTick((v) => v + 1), 1000);
    return () => { cancelled = true; clearInterval(pollTimer); clearInterval(beatTimer); clearInterval(tickTimer); };
  }, [open, currentRoomId, loadRoom, pullMessages]);

  async function withBusy(fn) {
    if (busy) return;
    setBusy(true); setNotice("");
    try { await fn(); } catch (error) { setNotice(errText(error)); } finally { if (aliveRef.current) setBusy(false); }
  }

  function enterRoom(detail) {
    cursorRef.current = 0;
    setMessages([]);
    setRoom(detail);
    detailAtRef.current = Date.now();
  }

  const createRoom = () => withBusy(async () => {
    const created = await roomApi.createStudyRoom({ title: title.trim() || "自习室" });
    setTitle("");
    enterRoom(created);
    await refreshLists();
  });
  const joinRoom = (id) => withBusy(async () => { enterRoom(await roomApi.getStudyRoom(id)); });
  const acceptInvite = (id) => withBusy(async () => { enterRoom(await roomApi.acceptStudyRoomInvitation(id)); await refreshLists(); });
  const declineInvite = (id) => withBusy(async () => { await roomApi.declineStudyRoomInvitation(id); await refreshLists(); });
  const invitePeer = () => withBusy(async () => { await roomApi.inviteStudyRoomStudent(room.id, uid.trim()); await loadRoom(room.id); setUid(""); setNotice("邀请已发送"); });
  const setState = (state) => withBusy(async () => { setMyState(state); await roomApi.updateStudyRoomState(room.id, state, statusMsg); await loadRoom(room.id); });
  const saveStatusMsg = () => withBusy(async () => { await roomApi.updateStudyRoomState(room.id, myState, statusMsg); await loadRoom(room.id); });
  const control = (action, extra) => withBusy(async () => { setRoom(await roomApi.controlStudyRoomTimer(room.id, action, extra)); detailAtRef.current = Date.now(); });
  const sendMsg = () => withBusy(async () => {
    const content = draft.trim();
    if (!content) return;
    const id = (globalThis.crypto?.randomUUID?.() || `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`);
    await roomApi.sendStudyRoomMessage(room.id, content, id);
    setDraft("");
    await pullMessages(room.id);
  });
  const leaveRoom = () => withBusy(async () => { await roomApi.leaveStudyRoom(room.id); setRoom(null); setMessages([]); await refreshLists(); });

  // 倒计时：以服务端 timer 为基准，本地每秒外推
  const isHost = room && identity && room.host_uid === identity.uid;
  let remaining = room?.timer?.remaining_seconds ?? 0;
  if (room?.timer?.running) {
    const elapsed = Math.floor((Date.now() - detailAtRef.current) / 1000);
    remaining = Math.max(0, remaining - elapsed);
  }
  void tick;

  return (
    <Modal title="多人自习室" onClose={onClose} className="study-room-modal" actions={<Button variant="quiet" onClick={onClose}>关闭</Button>}>
      {notice && <p className="study-room-notice" role="status">{notice}</p>}
      {!room ? (
        <div className="study-room-entry">
          <p className="study-room-hint">和同学进同一个自习室，互相看见谁在专注、共用一个番茄钟、发一句鼓励。不开启摄像头或音视频。</p>
          <div className="study-room-create">
            <input value={title} maxLength={200} onChange={(event) => setTitle(event.target.value)} placeholder="自习室名称，如：期末冲刺" aria-label="自习室名称" />
            <Button disabled={busy} onClick={createRoom} icon="PhPlus">创建</Button>
          </div>
          {identity && <p className="study-room-mine">我的 UID：<code>{identity.uid}</code></p>}
          {invitations.length > 0 && (
            <section className="study-room-invites">
              <h4>待接受的邀请</h4>
              {invitations.map((invitation) => (
                <div className="study-room-row" key={invitation.room_id}>
                  <span>{invitation.host_name} 邀请你进入「{invitation.title}」</span>
                  <span className="study-room-row-actions">
                    <Button disabled={busy} onClick={() => acceptInvite(invitation.room_id)}>接受</Button>
                    <Button variant="quiet" disabled={busy} onClick={() => declineInvite(invitation.room_id)}>拒绝</Button>
                  </span>
                </div>
              ))}
            </section>
          )}
          {rooms.length > 0 && (
            <section className="study-room-list">
              <h4>我的自习室</h4>
              {rooms.map((item) => (
                <div className="study-room-row" key={item.id}>
                  <span>{item.title} · {item.member_count} 人</span>
                  <Button variant="secondary" disabled={busy} onClick={() => joinRoom(item.id)}>进入</Button>
                </div>
              ))}
            </section>
          )}
        </div>
      ) : (
        <div className="study-room-live">
          <div className="study-room-head">
            <div>
              <h3>{room.title}</h3>
              <p className="study-room-hint">共享番茄钟：{room.focus_minutes} 分钟专注 / {room.break_minutes} 分钟休息</p>
            </div>
            <Button variant="quiet" disabled={busy} onClick={leaveRoom}>{isHost ? "结束自习室" : "离开"}</Button>
          </div>

          <div className={`study-room-timer phase-${room.timer.phase}`}>
            <span className="study-room-timer-phase">{room.timer.phase === "focus" ? "专注" : room.timer.phase === "break" ? "休息" : "待开始"}{room.timer.paused ? " · 已暂停" : ""}</span>
            <strong className="study-room-timer-value">{mmss(remaining)}</strong>
            {isHost ? (
              <span className="study-room-timer-actions">
                {room.timer.phase === "idle" && <Button disabled={busy} onClick={() => control("start_focus")} icon="PhPlay">开始专注</Button>}
                {room.timer.phase === "focus" && !room.timer.paused && <Button disabled={busy} onClick={() => control("pause")} icon="PhPause">暂停</Button>}
                {room.timer.phase === "focus" && room.timer.paused && <Button disabled={busy} onClick={() => control("resume")} icon="PhPlay">继续</Button>}
                {room.timer.phase === "focus" && <Button variant="secondary" disabled={busy} onClick={() => control("start_break")} icon="PhCoffee">开始休息</Button>}
                {room.timer.phase === "break" && !room.timer.paused && <Button disabled={busy} onClick={() => control("pause")} icon="PhPause">暂停</Button>}
                {room.timer.phase === "break" && room.timer.paused && <Button disabled={busy} onClick={() => control("resume")} icon="PhPlay">继续</Button>}
                {room.timer.phase !== "idle" && <Button variant="quiet" disabled={busy} onClick={() => control("reset")}>重置</Button>}
              </span>
            ) : (
              <span className="study-room-timer-note">由发起人控制计时</span>
            )}
          </div>

          <section className="study-room-members">
            <h4>成员（{room.members.filter((m) => m.status === "accepted").length}）</h4>
            {room.members.filter((m) => m.status === "accepted").map((member) => (
              <div className={`study-room-member ${member.online ? "" : "is-away"}`} key={member.uid}>
                <span className={`study-room-badge ${STATE_TONE[member.study_state] || "tone-muted"}`}>{member.online ? STATE_LABEL[member.study_state] : "离开"}</span>
                <strong>{member.name}{member.uid === room.host_uid ? "（发起人）" : ""}</strong>
                {member.status_message && <small>{member.status_message}</small>}
              </div>
            ))}
          </section>

          <section className="study-room-my-state">
            <h4>我的状态</h4>
            <div className="study-room-state-buttons">
              {Object.entries(STATE_LABEL).map(([key, label]) => (
                <button key={key} type="button" className={myState === key ? "is-active" : ""} disabled={busy} onClick={() => setState(key)}>{label}</button>
              ))}
            </div>
            <div className="study-room-status-msg">
              <input value={statusMsg} maxLength={140} onChange={(event) => setStatusMsg(event.target.value)} placeholder="状态语（可选），如：冲刺数学" aria-label="状态语" />
              <Button variant="quiet" disabled={busy} onClick={saveStatusMsg}>保存状态语</Button>
            </div>
          </section>

          {isHost && (
            <section className="study-room-invite-peer">
              <h4>邀请同学</h4>
              <div className="study-room-create">
                <input value={uid} maxLength={128} onChange={(event) => setUid(event.target.value)} placeholder="输入同学 UID" aria-label="同学 UID" />
                <Button disabled={busy || !uid.trim()} onClick={invitePeer} icon="PhPaperPlaneTilt">邀请</Button>
              </div>
            </section>
          )}

          <section className="study-room-messages">
            <h4>互相鼓励</h4>
            <div className="study-room-message-log" role="log" aria-live="polite">
              {messages.length === 0 ? <p className="study-room-hint">还没有消息，发一句鼓励吧。</p> : messages.map((message) => (
                <div className="study-room-message" key={message.id}>
                  <strong>{message.name}</strong><span>{message.content}</span>
                </div>
              ))}
            </div>
            <div className="study-room-status-msg">
              <input value={draft} maxLength={2000} onChange={(event) => setDraft(event.target.value)} placeholder="说点什么鼓励大家…" aria-label="房内消息" />
              <Button disabled={busy || !draft.trim()} onClick={sendMsg} icon="PhPaperPlaneTilt">发送</Button>
            </div>
          </section>
        </div>
      )}
    </Modal>
  );
}
