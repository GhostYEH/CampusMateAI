export const LEARNING_ROOM_CHANNEL = "campusmate-learning-room-v1";

export function isLearningRoomMessage(event, origin, frameWindow) {
  return Boolean(frameWindow && event.source === frameWindow && event.origin === origin &&
    event.data?.channel === LEARNING_ROOM_CHANNEL && typeof event.data.type === "string");
}

export function learningSpaceEmbedUrl(origin, parentOrigin) {
  const url = new URL(origin);
  url.searchParams.set("campusmateOrigin", parentOrigin);
  return url.href;
}

export function mergeLearningMessages(previous, incoming) {
  const byId = new Map(previous.map((message) => [message.id, message]));
  incoming.forEach((message) => byId.set(message.id, message));
  return [...byId.values()].sort((a, b) => a.id - b.id);
}
