import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  campusmateParentOrigin,
  CAMPUSMATE_CHANNEL,
  classroomMediaStatus,
  requestClassroomEntry,
} from '@/lib/classroom/campusmate-entry';

afterEach(() => vi.unstubAllGlobals());

describe('CampusMate embedded classroom admission', () => {
  it('waits for this classroom media while ignoring another classroom tasks', () => {
    const tasks = {
      image: { stageId: 'current', status: 'generating' },
      other: { stageId: 'other', status: 'failed' },
    };
    expect(classroomMediaStatus('current', tasks)).toEqual({ pending: true, failed: false });
    tasks.image.status = 'done';
    expect(classroomMediaStatus('current', tasks)).toEqual({ pending: false, failed: false });
    tasks.image.status = 'failed';
    expect(classroomMediaStatus('current', tasks)).toEqual({ pending: false, failed: true });
  });
  it('keeps standalone classroom navigation unchanged', async () => {
    const navigate = vi.fn();
    await requestClassroomEntry('local-stage', navigate);
    expect(navigate).toHaveBeenCalledWith('/classroom/local-stage');
  });

  it('waits for the real parent to approve entry and rejects forged replies', async () => {
    const origin = 'https://campus.example.edu';
    const parent = { postMessage: vi.fn() };
    let receive: ((event: MessageEvent) => void) | undefined;
    const remove = vi.fn();
    vi.stubGlobal('window', {
      parent,
      location: { search: `?campusmateOrigin=${encodeURIComponent(origin)}` },
      addEventListener: (_: string, fn: typeof receive) => {
        receive = fn;
      },
      removeEventListener: remove,
    });
    const navigate = vi.fn();
    const pending = requestClassroomEntry('shared-stage', navigate);
    const request = parent.postMessage.mock.calls[0][0];
    expect(parent.postMessage.mock.calls[0][1]).toBe(origin);
    expect(request.type).toBe('entry');
    const data = { channel: CAMPUSMATE_CHANNEL, requestId: request.requestId, type: 'enter' };
    receive!({ source: {}, origin, data } as MessageEvent);
    receive!({ source: parent, origin: 'https://evil.invalid', data } as unknown as MessageEvent);
    expect(navigate).not.toHaveBeenCalled();
    receive!({ source: parent, origin, data } as unknown as MessageEvent);
    await pending;
    expect(navigate).toHaveBeenCalledWith('/classroom/shared-stage');
    expect(remove).toHaveBeenCalled();
  });

  it('cancels classroom navigation when the invitation dialog closes', async () => {
    const parent = { postMessage: vi.fn() };
    let receive: ((event: MessageEvent) => void) | undefined;
    const origin = 'https://campus.example.edu';
    vi.stubGlobal('window', {
      parent,
      location: { search: `?campusmateOrigin=${encodeURIComponent(origin)}` },
      addEventListener: (_: string, fn: typeof receive) => {
        receive = fn;
      },
      removeEventListener: vi.fn(),
    });
    const navigate = vi.fn();
    const pending = requestClassroomEntry('stage', navigate);
    const requestId = parent.postMessage.mock.calls[0][0].requestId;
    receive!({
      source: parent,
      origin,
      data: { channel: CAMPUSMATE_CHANNEL, requestId, type: 'cancel' },
    } as unknown as MessageEvent);
    await pending;
    expect(navigate).not.toHaveBeenCalled();
  });

  it('does not treat a non-origin URL as the trusted parent', () => {
    vi.stubGlobal('window', {
      parent: {},
      location: { search: '?campusmateOrigin=https%3A%2F%2Fcampus.example.edu%2Fpath' },
    });
    expect(campusmateParentOrigin()).toBeNull();
  });
});
