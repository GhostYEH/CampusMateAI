import { client } from "./api.js";

const base = "/magicclass/learning-space";
const roomPath = (id) => `${base}/rooms/${encodeURIComponent(id)}`;
const dataOf = (response) => response.data;
export const getLearningIdentity = () => client.get(`${base}/identity`).then(dataOf);
export const findLearningStudent = (uid) => client.get(`${base}/students/${encodeURIComponent(uid.trim())}`).then(dataOf);
export const listLearningRooms = () => client.get(`${base}/rooms`).then(dataOf);
export const listLearningInvitations = () => client.get(`${base}/invitations`).then(dataOf);
export const getLearningRoom = (id) => client.get(roomPath(id)).then(dataOf);
export const inviteLearningStudent = (id, uid) => client.post(`${roomPath(id)}/invitations`, { uid }).then(dataOf);
export const acceptLearningInvitation = (id) => client.post(`${base}/invitations/${encodeURIComponent(id)}/accept`).then(dataOf);
export const declineLearningInvitation = (id) => client.post(`${base}/invitations/${encodeURIComponent(id)}/decline`);
export const leaveLearningRoom = (id) => client.post(`${roomPath(id)}/leave`);
export const getLearningArchive = (id) => client.get(`${roomPath(id)}/archive`, { responseType: "blob" }).then(dataOf);
export const setLearningCursor = (id, sceneIndex) => client.patch(`${roomPath(id)}/cursor`, { scene_index: sceneIndex });
export const getLearningMessages = (id, after = 0) => client.get(`${roomPath(id)}/messages`, { params: { after } }).then(dataOf);
export const sendLearningMessage = (id, content, clientId) => client.post(`${roomPath(id)}/messages`, { content, client_id: clientId }).then(dataOf);

export function createLearningRoom({ archive, title, stageId }) {
  const form = new FormData();
  form.append("file", archive, "classroom.maic.zip");
  form.append("title", title.slice(0, 200));
  form.append("stage_id", stageId);
  return client.post(`${base}/rooms`, form).then(dataOf);
}
