export const CAMPUSMATE_CHANNEL = 'campusmate-learning-room-v1';

export function classroomMediaStatus(
  stageId: string | undefined,
  tasks: Record<string, { stageId: string; status: string }>,
) {
  const relevant = Object.values(tasks).filter((task) => task.stageId === stageId);
  return {
    pending: relevant.some((task) => task.status === 'pending' || task.status === 'generating'),
    failed: relevant.some((task) => task.status === 'failed'),
  };
}

/** The parent supplies its public origin; no credentials cross this boundary. */
export function campusmateParentOrigin(): string | null {
  if (typeof window === 'undefined' || window.parent === window) return null;
  try {
    const value =
      new URLSearchParams(window.location.search).get('campusmateOrigin') ??
      sessionStorage.getItem('campusmate-parent-origin');
    if (!value) return null;
    const url = new URL(value);
    if (!['https:', 'http:'].includes(url.protocol) || url.origin !== value) return null;
    return value;
  } catch {
    return null;
  }
}

export async function requestClassroomEntry(stageId: string, navigate: (url: string) => void) {
  const origin = campusmateParentOrigin();
  if (!origin) {
    navigate(`/classroom/${stageId}`);
    return;
  }
  const requestId = crypto.randomUUID();
  await new Promise<void>((resolve) => {
    const listener = (event: MessageEvent) => {
      if (
        event.source !== window.parent ||
        event.origin !== origin ||
        event.data?.channel !== CAMPUSMATE_CHANNEL ||
        event.data.requestId !== requestId
      )
        return;
      if (!['enter', 'cancel'].includes(event.data.type)) return;
      window.removeEventListener('message', listener);
      if (event.data.type === 'enter') navigate(`/classroom/${stageId}`);
      resolve();
    };
    window.addEventListener('message', listener);
    window.parent.postMessage(
      { channel: CAMPUSMATE_CHANNEL, type: 'entry', stageId, requestId },
      origin,
    );
  });
}
