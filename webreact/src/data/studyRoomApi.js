import { client } from "./api.js";

/**
 * 多人在线自习室（互相监督）。
 *
 * 后端契约见 docs/api/05-study.md「多人在线自习室」。纯 HTTP 轮询：客户端定时
 * 读详情与消息、并每约 15 秒上报 heartbeat；没有 SSE / WebSocket 与音视频。
 */
const base = "/study/rooms";
const roomPath = (id) => `${base}/${encodeURIComponent(id)}`;
const dataOf = (response) => response.data;

export const getStudyRoomIdentity = () => client.get(`${base}/identity`).then(dataOf);
export const findStudyRoomStudent = (uid) => client.get(`${base}/students/${encodeURIComponent(uid.trim())}`).then(dataOf);
export const listStudyRooms = () => client.get(`${base}/`).then(dataOf);
export const listStudyRoomInvitations = () => client.get(`${base}/invitations`).then(dataOf);
export const createStudyRoom = ({ title, focusMinutes = 25, breakMinutes = 5 }) =>
  client.post(`${base}/`, { title: title.slice(0, 200), focus_minutes: focusMinutes, break_minutes: breakMinutes }).then(dataOf);
export const getStudyRoom = (id) => client.get(roomPath(id)).then(dataOf);
export const inviteStudyRoomStudent = (id, uid) => client.post(`${roomPath(id)}/invitations`, { uid }).then(dataOf);
export const acceptStudyRoomInvitation = (id) => client.post(`${base}/invitations/${encodeURIComponent(id)}/accept`).then(dataOf);
export const declineStudyRoomInvitation = (id) => client.post(`${base}/invitations/${encodeURIComponent(id)}/decline`);
export const updateStudyRoomState = (id, studyState, statusMessage = null) =>
  client.patch(`${roomPath(id)}/state`, { study_state: studyState, status_message: statusMessage });
export const heartbeatStudyRoom = (id) => client.post(`${roomPath(id)}/heartbeat`).then(dataOf);
export const controlStudyRoomTimer = (id, action, extra = {}) =>
  client.post(`${roomPath(id)}/timer`, { action, ...extra }).then(dataOf);
export const getStudyRoomMessages = (id, after = 0) => client.get(`${roomPath(id)}/messages`, { params: { after } }).then(dataOf);
export const sendStudyRoomMessage = (id, content, clientId) => client.post(`${roomPath(id)}/messages`, { content, client_id: clientId }).then(dataOf);
export const leaveStudyRoom = (id) => client.post(`${roomPath(id)}/leave`);

/** 合并重叠消息页：按服务端 id 去重并保持升序。 */
export function mergeStudyRoomMessages(previous, incoming) {
  const byId = new Map(previous.map((message) => [message.id, message]));
  incoming.forEach((message) => byId.set(message.id, message));
  return [...byId.values()].sort((a, b) => a.id - b.id);
}
