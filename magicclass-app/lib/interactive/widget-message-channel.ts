/** Both protocols occur in persisted classrooms (the original 3D template used action/payload). */
export function widgetMessage(type: string, payload: Record<string, unknown>) {
  const target = typeof payload.target === 'string' ? payload.target.replace(/^#/, '') : payload.target;
  return {
    ...payload,
    type,
    action: type,
    payload: {
      ...payload,
      ...(payload.state && typeof payload.state === 'object' ? payload.state : {}),
      elementId: target,
      text: payload.content,
      ...(type === 'HIGHLIGHT_ELEMENT' ? { highlight: true } : {}),
    },
  };
}

let nextDocumentToken = 0;

/** A channel belongs to one iframe document; never replay old actions into edited HTML. */
export class WidgetMessageChannel {
  readonly token = `interactive-document-${++nextDocumentToken}`;
  private ready = false;
  private pending: ReturnType<typeof widgetMessage>[] = [];

  constructor(private readonly post: (message: ReturnType<typeof widgetMessage>) => void) {}

  send(type: string, payload: Record<string, unknown>) {
    const message = widgetMessage(type, payload);
    if (this.ready) this.post(message);
    else this.pending.push(message);
  }

  markReady() {
    if (this.ready) return;
    this.ready = true;
    for (const message of this.pending.splice(0)) this.post(message);
  }
}
