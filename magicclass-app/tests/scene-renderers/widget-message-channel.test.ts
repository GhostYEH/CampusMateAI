import { describe, expect, it } from 'vitest';
import { WidgetMessageChannel } from '@/lib/interactive/widget-message-channel';

describe('widget document messaging', () => {
  it('queues early lecture actions in order and replays once when ready', () => {
    const posts: unknown[] = [];
    const channel = new WidgetMessageChannel((message) => posts.push(message));
    channel.send('HIGHLIGHT_ELEMENT', { target: '#cell', content: '重点' });
    channel.send('ANNOTATE_ELEMENT', { target: '#cell', content: '细胞膜' });
    expect(posts).toEqual([]);
    channel.markReady();
    channel.markReady();
    expect(posts).toHaveLength(2);
    expect(posts[0]).toMatchObject({ type: 'HIGHLIGHT_ELEMENT', target: '#cell', payload: { elementId: 'cell', highlight: true } });
    expect(posts[1]).toMatchObject({ action: 'ANNOTATE_ELEMENT', payload: { elementId: 'cell', text: '细胞膜' } });
    channel.send('SET_WIDGET_STATE', { state: { cameraPosition: [1, 2, 3], scale: 2 } });
    expect(posts[2]).toMatchObject({ state: { scale: 2 }, payload: { cameraPosition: [1, 2, 3], scale: 2 } });
  });

  it('an edited document has a different token and never inherits old queued actions', () => {
    const posts: unknown[] = [];
    const old = new WidgetMessageChannel((message) => posts.push(message));
    old.send('ANNOTATE_ELEMENT', { target: '#old', content: 'old' });
    const edited = new WidgetMessageChannel((message) => posts.push(message));
    expect(edited.token).not.toBe(old.token);
    edited.markReady();
    expect(posts).toEqual([]);
  });
});
