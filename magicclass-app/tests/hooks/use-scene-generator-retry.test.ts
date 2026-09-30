import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import type { SceneOutline } from '@/lib/types/generation';
import { createAdaptiveConcurrencyLimiter } from '@/lib/utils/concurrency';

const mocks = vi.hoisted(() => ({
  getCurrentModelConfig: vi.fn(),
  settingsState: vi.fn(),
  audioPut: vi.fn(),
  audioDelete: vi.fn(),
  poolPut: vi.fn(),
  poolReplace: vi.fn(),
  poolRemove: vi.fn(),
  isTTSProviderEnabled: vi.fn(),
  pickNarratorAgent: vi.fn(),
  resolveAgentVoiceOptions: vi.fn(),
  listAgents: vi.fn(),
  toastWarning: vi.fn(),
}));

vi.mock('@/lib/utils/model-config', () => ({
  getCurrentModelConfig: mocks.getCurrentModelConfig,
}));

vi.mock('@/lib/store/settings', () => ({
  useSettingsStore: {
    getState: mocks.settingsState,
  },
}));

vi.mock('@/lib/utils/database', () => ({
  db: {
    audioFiles: {
      put: mocks.audioPut,
      delete: mocks.audioDelete,
    },
  },
}));

vi.mock('@/lib/media/asset-pool', () => ({
  putAsset: mocks.poolPut,
  replaceAsset: mocks.poolReplace,
  removeAsset: mocks.poolRemove,
}));

vi.mock('@/lib/audio/provider-enablement', () => ({
  isTTSProviderEnabled: mocks.isTTSProviderEnabled,
}));

vi.mock('@/lib/audio/agent-voice', () => ({
  pickNarratorAgent: mocks.pickNarratorAgent,
  resolveAgentVoiceOptions: mocks.resolveAgentVoiceOptions,
}));

vi.mock('@/lib/orchestration/registry/store', () => ({
  useAgentRegistry: {
    getState: () => ({
      listAgents: mocks.listAgents,
    }),
  },
}));

vi.mock('sonner', () => ({ toast: { warning: mocks.toastWarning } }));

const mockFetch = vi.fn() as Mock;
vi.stubGlobal('fetch', mockFetch);

const outline = {
  id: 'outline-1',
  type: 'slide',
  title: 'Retry Scene',
  description: 'Retry transient failures',
  keyPoints: ['retry'],
  order: 2,
} as SceneOutline;

const retryOptions = {
  maxRetries: 1,
  sleep: async () => undefined,
  random: () => 0,
};

function jsonResponse(status: number, body: unknown, headers?: Record<string, string>) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 429 ? 'Too Many Requests' : status === 401 ? 'Unauthorized' : 'OK',
    headers: new Headers(headers),
    json: async () => body,
  };
}

describe('browser scene generation retry wrappers', () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mocks.audioPut.mockReset();
    mocks.audioDelete.mockReset().mockResolvedValue(undefined);
    mocks.poolPut.mockReset();
    mocks.poolReplace.mockReset().mockResolvedValue(undefined);
    mocks.poolRemove.mockReset().mockResolvedValue(undefined);
    mocks.poolPut.mockResolvedValue('ast_audio_allocated');
    mocks.getCurrentModelConfig.mockReturnValue({});
    mocks.settingsState.mockReturnValue({
      imageProviderId: '',
      imageProvidersConfig: {},
      imageGenerationEnabled: false,
      videoProviderId: '',
      videoProvidersConfig: {},
      videoGenerationEnabled: false,
      ttsProviderId: 'server-tts',
      ttsProvidersConfig: {
        'server-tts': {
          apiKey: 'tts-key',
          modelId: 'tts-model',
        },
      },
      ttsVoice: 'narrator',
      ttsSpeed: 1,
    });
    mocks.isTTSProviderEnabled.mockReturnValue(true);
    mocks.pickNarratorAgent.mockReturnValue(undefined);
    mocks.resolveAgentVoiceOptions.mockResolvedValue({});
    mocks.listAgents.mockReturnValue([]);
    mocks.toastWarning.mockReset();
  });

  it('retries transient scene content HTTP failures before returning success', async () => {
    const { fetchSceneContent } = await import('@/lib/hooks/use-scene-generator');
    mockFetch
      .mockResolvedValueOnce(jsonResponse(429, { error: 'rate limited' }))
      .mockResolvedValueOnce(jsonResponse(200, { success: true, content: { elements: [] } }));

    const result = await fetchSceneContent(
      {
        outline,
        allOutlines: [outline],
        stageId: 'stage-1',
        stageInfo: { name: 'Retry Course' },
      },
      undefined,
      retryOptions,
    );

    expect(result).toMatchObject({ success: true, content: { elements: [] } });
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it('reduces content request concurrency and honors Retry-After on HTTP 429', async () => {
    vi.useFakeTimers();
    try {
      const { fetchSceneContent } = await import('@/lib/hooks/use-scene-generator');
      const limiter = createAdaptiveConcurrencyLimiter(8);
      mockFetch
        .mockResolvedValueOnce(jsonResponse(429, { error: 'rate limited' }, { 'Retry-After': '2' }))
        .mockResolvedValueOnce(jsonResponse(200, { success: true, content: { elements: [] } }));

      const generation = fetchSceneContent(
        {
          outline,
          allOutlines: [outline],
          stageId: 'stage-1',
          stageInfo: { name: 'Retry Course' },
        },
        undefined,
        retryOptions,
        limiter,
      );
      await vi.advanceTimersByTimeAsync(0);
      expect(limiter.limit).toBe(4);
      expect(mockFetch).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(1_999);
      expect(mockFetch).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(1);
      await expect(generation).resolves.toMatchObject({ success: true });
      expect(mockFetch).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it('shares the eight-request cap between scene content and actions', async () => {
    const { fetchSceneContent, fetchSceneActions } =
      await import('@/lib/hooks/use-scene-generator');
    const limiter = createAdaptiveConcurrencyLimiter(8);
    const releases: Array<() => void> = [];
    let active = 0;
    let peak = 0;
    mockFetch.mockImplementation(
      (url: string) =>
        new Promise((resolve) => {
          active++;
          peak = Math.max(peak, active);
          releases.push(() => {
            active--;
            resolve(
              url.endsWith('scene-actions')
                ? jsonResponse(200, { success: true, scene: {} })
                : jsonResponse(200, { success: true, content: { elements: [] } }),
            );
          });
        }),
    );

    const contents = Array.from({ length: 8 }, (_, index) =>
      fetchSceneContent(
        {
          outline: { ...outline, id: `outline-${index}` },
          allOutlines: [outline],
          stageId: 'stage-1',
          stageInfo: { name: 'Retry Course' },
        },
        undefined,
        { ...retryOptions, maxRetries: 0 },
        limiter,
      ),
    );
    const actions = fetchSceneActions(
      {
        outline,
        allOutlines: [outline],
        content: { elements: [] },
        stageId: 'stage-1',
      },
      undefined,
      { ...retryOptions, maxRetries: 0 },
      limiter,
    );

    await vi.waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(8));
    expect(peak).toBe(8);
    releases.shift()!();
    await vi.waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(9));
    expect(peak).toBe(8);
    releases.splice(0).forEach((release) => release());
    await expect(Promise.all([...contents, actions])).resolves.toHaveLength(9);
  });

  it('reduces the shared cap when scene actions receive HTTP 429', async () => {
    vi.useFakeTimers();
    try {
      const { fetchSceneActions } = await import('@/lib/hooks/use-scene-generator');
      const limiter = createAdaptiveConcurrencyLimiter(8);
      mockFetch
        .mockResolvedValueOnce(jsonResponse(429, { error: 'rate limited' }, { 'Retry-After': '2' }))
        .mockResolvedValueOnce(jsonResponse(200, { success: true, scene: {} }));

      const generation = fetchSceneActions(
        {
          outline,
          allOutlines: [outline],
          content: { elements: [] },
          stageId: 'stage-1',
        },
        undefined,
        retryOptions,
        limiter,
      );
      await vi.advanceTimersByTimeAsync(0);
      expect(limiter.limit).toBe(4);
      expect(mockFetch).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(1_999);
      expect(mockFetch).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(1);
      await expect(generation).resolves.toMatchObject({ success: true });
      expect(mockFetch).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it('does not retry permanent scene action HTTP failures', async () => {
    const { fetchSceneActions } = await import('@/lib/hooks/use-scene-generator');
    mockFetch.mockResolvedValue(jsonResponse(401, { error: 'unauthorized' }));

    const result = await fetchSceneActions(
      {
        outline,
        allOutlines: [outline],
        content: { elements: [] },
        stageId: 'stage-1',
      },
      undefined,
      retryOptions,
    );

    expect(result).toMatchObject({ success: false, error: 'unauthorized' });
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('preserves scene content error metadata for localized UI messages', async () => {
    const { fetchSceneContent } = await import('@/lib/hooks/use-scene-generator');
    mockFetch.mockResolvedValue(
      jsonResponse(429, {
        success: false,
        errorCode: 'RATE_LIMITED',
        error: 'Upstream rate limit reached. Please try again shortly.',
      }),
    );

    const result = await fetchSceneContent(
      {
        outline,
        allOutlines: [outline],
        stageId: 'stage-1',
        stageInfo: { name: 'Retry Course' },
      },
      undefined,
      { ...retryOptions, maxRetries: 0 },
    );

    expect(result).toMatchObject({
      success: false,
      errorCode: 'RATE_LIMITED',
      statusCode: 429,
    });
  });

  it('preserves internal scene content errors for localized fallback messages', async () => {
    const { fetchSceneContent } = await import('@/lib/hooks/use-scene-generator');
    mockFetch.mockResolvedValue(
      jsonResponse(500, {
        success: false,
        errorCode: 'INTERNAL_ERROR',
        error: 'Scene generation failed. Please try again.',
      }),
    );

    const result = await fetchSceneContent(
      {
        outline,
        allOutlines: [outline],
        stageId: 'stage-1',
        stageInfo: { name: 'Retry Course' },
      },
      undefined,
      { ...retryOptions, maxRetries: 0 },
    );

    expect(result).toMatchObject({
      success: false,
      errorCode: 'INTERNAL_ERROR',
      statusCode: 500,
    });
  });

  it('rethrows an aborted scene content request', async () => {
    const { fetchSceneContent } = await import('@/lib/hooks/use-scene-generator');
    const abort = Object.assign(new Error('Aborted'), { name: 'AbortError' });
    mockFetch.mockRejectedValueOnce(abort);

    await expect(
      fetchSceneContent(
        {
          outline,
          allOutlines: [outline],
          stageId: 'stage-1',
          stageInfo: { name: 'Retry Course' },
        },
        undefined,
        retryOptions,
      ),
    ).rejects.toBe(abort);

    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('rethrows an aborted scene actions request', async () => {
    const { fetchSceneActions } = await import('@/lib/hooks/use-scene-generator');
    const abort = Object.assign(new Error('Aborted'), { name: 'AbortError' });
    mockFetch.mockRejectedValueOnce(abort);

    await expect(
      fetchSceneActions(
        {
          outline,
          allOutlines: [outline],
          content: { elements: [] },
          stageId: 'stage-1',
        },
        undefined,
        retryOptions,
      ),
    ).rejects.toBe(abort);

    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('keeps reduced TTS concurrency for later scenes in the course', async () => {
    vi.useFakeTimers();
    try {
      const { generateTTSForScene } = await import('@/lib/hooks/use-scene-generator');
      const limiter = createAdaptiveConcurrencyLimiter(8);
      const makeScene = (order: number, count: number) =>
        ({
          id: `scene-${order}`,
          stageId: 'stage-1',
          order,
          actions: Array.from({ length: count }, (_, index) => ({
            id: `speech-${index}`,
            type: 'speech',
            text: 'Hello class',
          })),
        }) as Parameters<typeof generateTTSForScene>[0];
      const audioResponse = () =>
        jsonResponse(200, { success: true, base64: btoa('audio-data'), format: 'wav' });
      mockFetch
        .mockResolvedValueOnce(jsonResponse(429, { error: 'rate limited' }))
        .mockResolvedValueOnce(audioResponse());

      const generation = generateTTSForScene(
        makeScene(1, 1),
        undefined,
        undefined,
        retryOptions,
        limiter,
      );
      await vi.advanceTimersByTimeAsync(0);
      expect(limiter.limit).toBe(4);
      expect(mockFetch).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(999);
      expect(mockFetch).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(1);
      await expect(generation).resolves.toMatchObject({ success: true });
      expect(mockFetch).toHaveBeenCalledTimes(2);

      const releases: Array<() => void> = [];
      mockFetch.mockImplementation(
        () => new Promise((resolve) => releases.push(() => resolve(audioResponse()))),
      );
      const nextScene = generateTTSForScene(
        makeScene(2, 5),
        undefined,
        undefined,
        retryOptions,
        limiter,
      );
      await vi.advanceTimersByTimeAsync(0);
      expect(releases).toHaveLength(4);
      releases.splice(0).forEach((release) => release());
      await vi.advanceTimersByTimeAsync(0);
      expect(releases).toHaveLength(1);
      releases.splice(0).forEach((release) => release());
      await expect(nextScene).resolves.toMatchObject({ success: true });
    } finally {
      vi.useRealTimers();
    }
  });

  it('retries transient TTS failures before storing audio', async () => {
    const { generateAndStoreTTS } = await import('@/lib/hooks/use-scene-generator');
    mockFetch
      .mockResolvedValueOnce(jsonResponse(503, { error: 'provider overloaded' }))
      .mockResolvedValueOnce(
        jsonResponse(200, {
          success: true,
          base64: btoa('audio-data'),
          format: 'wav',
        }),
      );

    const audioId = await generateAndStoreTTS(
      'tts_s2_action_1',
      'Hello class',
      'English',
      undefined,
      retryOptions,
    );

    expect(audioId).toBe('tts_s2_action_1');
    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(mocks.poolPut).not.toHaveBeenCalled();
    expect(mocks.audioPut).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 'tts_s2_action_1',
        format: 'wav',
      }),
    );
  });

  it('falls back once from a missing narrator clone to the global voice', async () => {
    const { generateAndStoreTTS } = await import('@/lib/hooks/use-scene-generator');
    mocks.settingsState.mockReturnValue({
      ...mocks.settingsState(),
      ttsProviderId: 'qwen-tts',
      ttsVoice: 'Cherry',
      ttsProvidersConfig: {
        'qwen-tts': { apiKey: 'tts-key', modelId: 'qwen3-tts-vc-2026-01-22' },
      },
    });
    mocks.pickNarratorAgent.mockReturnValue({
      id: 'teacher-missing-clone',
      role: 'teacher',
      voiceConfig: { providerId: 'qwen-tts', voiceId: 'deleted-clone-id' },
    });
    mockFetch
      .mockResolvedValueOnce(
        jsonResponse(400, {
          errorCode: 'QWEN_VC_VOICE_NOT_FOUND',
          error: 'The cloned Qwen voice no longer exists.',
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse(200, { success: true, base64: btoa('fallback-audio'), format: 'wav' }),
      );

    await expect(
      generateAndStoreTTS('request-fallback', 'Hello class', undefined, undefined, {
        ...retryOptions,
        maxRetries: 0,
      }),
    ).resolves.toBe('request-fallback');
    expect(mockFetch).toHaveBeenCalledTimes(2);
    const firstBody = JSON.parse(String(mockFetch.mock.calls[0][1]?.body));
    const secondBody = JSON.parse(String(mockFetch.mock.calls[1][1]?.body));
    expect(firstBody).toMatchObject({
      ttsVoice: 'deleted-clone-id',
      ttsModelId: 'qwen3-tts-vc-2026-01-22',
    });
    expect(secondBody).toMatchObject({ ttsVoice: 'Cherry', ttsModelId: 'qwen3-tts-flash' });
    expect(mocks.toastWarning).toHaveBeenCalledOnce();
  });

  it('stores directly in Dexie without consulting the asset pool', async () => {
    const { generateAndStoreTTS } = await import('@/lib/hooks/use-scene-generator');
    mockFetch.mockResolvedValue(
      jsonResponse(200, {
        success: true,
        base64: btoa('audio-data'),
        format: 'wav',
      }),
    );
    mocks.poolPut.mockRejectedValueOnce(new Error('pool unavailable'));

    await expect(generateAndStoreTTS('request-1', 'Hello class')).resolves.toBe('request-1');
    expect(mocks.poolPut).not.toHaveBeenCalled();
    expect(mocks.audioPut).toHaveBeenCalledOnce();
  });

  it('does not report an allocated id when the compatibility write fails', async () => {
    const { generateAndStoreTTS } = await import('@/lib/hooks/use-scene-generator');
    mockFetch.mockResolvedValue(
      jsonResponse(200, {
        success: true,
        base64: btoa('audio-data'),
        format: 'wav',
      }),
    );
    mocks.audioPut.mockRejectedValueOnce(new Error('Dexie unavailable'));

    await expect(generateAndStoreTTS('request-1', 'Hello class')).rejects.toThrow(
      'Dexie unavailable',
    );
    expect(mocks.poolPut).not.toHaveBeenCalled();
    expect(mocks.poolRemove).not.toHaveBeenCalled();
  });

  it('reclaims earlier allocations when partial scene synthesis fails', async () => {
    const { generateTTSForScene } = await import('@/lib/hooks/use-scene-generator');
    mocks.poolPut.mockResolvedValueOnce('ast_first_audio');
    mockFetch
      .mockResolvedValueOnce(
        jsonResponse(200, {
          success: true,
          base64: btoa('first-audio'),
          format: 'wav',
        }),
      )
      .mockResolvedValueOnce(jsonResponse(401, { error: 'second speech rejected' }));
    const scene = {
      id: 'scene-1',
      stageId: 'stage-1',
      type: 'slide',
      title: 'Scene',
      order: 1,
      content: { type: 'slide', canvas: { id: 'slide-1', elements: [] } },
      actions: [
        { id: 'speech-1', type: 'speech', text: 'First line' },
        { id: 'speech-2', type: 'speech', text: 'Second line' },
      ],
    } as unknown as Parameters<typeof generateTTSForScene>[0];

    const result = await generateTTSForScene(scene, 'English', undefined, {
      ...retryOptions,
      maxRetries: 0,
    });

    expect(result).toMatchObject({ success: false, failedCount: 1 });
    expect(mocks.poolRemove).not.toHaveBeenCalled();
    expect(mocks.audioDelete).toHaveBeenCalledExactlyOnceWith('tts_s1_speech-1');
    expect(scene.actions?.every((action) => !('audioId' in action))).toBe(true);
  });

  it('waits for parallel TTS workers before rolling back an abandoned scene', async () => {
    const { generateTTSForScene } = await import('@/lib/hooks/use-scene-generator');
    mocks.settingsState.mockReturnValue({
      ...mocks.settingsState(),
      parallelSceneConcurrency: 2,
    });
    const abort = Object.assign(new Error('Aborted'), { name: 'AbortError' });
    let releaseSibling!: () => void;
    const siblingMayFinish = new Promise<void>((resolve) => {
      releaseSibling = resolve;
    });
    mockFetch.mockRejectedValueOnce(abort).mockImplementationOnce(async () => {
      await siblingMayFinish;
      return jsonResponse(200, {
        success: true,
        base64: btoa('late-audio'),
        format: 'wav',
      });
    });
    mocks.poolPut.mockResolvedValueOnce('ast_late_audio');
    const scene = {
      id: 'scene-1',
      stageId: 'stage-1',
      type: 'slide',
      title: 'Scene',
      order: 1,
      content: { type: 'slide', canvas: { id: 'slide-1', elements: [] } },
      actions: [
        { id: 'speech-1', type: 'speech', text: 'Aborted line' },
        { id: 'speech-2', type: 'speech', text: 'Late line' },
      ],
    } as unknown as Parameters<typeof generateTTSForScene>[0];

    const generating = generateTTSForScene(scene, 'English', undefined, retryOptions);
    await vi.waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2));
    expect(mocks.poolRemove).not.toHaveBeenCalled();

    releaseSibling();
    await expect(generating).rejects.toBe(abort);

    expect(mocks.poolRemove).not.toHaveBeenCalled();
    expect(mocks.audioDelete).toHaveBeenCalledExactlyOnceWith('tts_s1_speech-2');
    expect(scene.actions?.every((action) => !('audioId' in action))).toBe(true);
  });

  it('replaces allocated audio under the stable id and refreshes its compatibility row', async () => {
    const { generateAndStoreTTS } = await import('@/lib/hooks/use-scene-generator');
    mockFetch.mockResolvedValue(
      jsonResponse(200, {
        success: true,
        base64: btoa('replacement-audio'),
        format: 'wav',
      }),
    );

    await expect(
      generateAndStoreTTS(
        'request-1',
        'Updated class',
        'English',
        undefined,
        undefined,
        'ast_stable_audio',
      ),
    ).resolves.toBe('ast_stable_audio');

    expect(mocks.poolPut).not.toHaveBeenCalled();
    expect(mocks.poolReplace).not.toHaveBeenCalled();
    expect(mocks.audioPut).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ id: 'ast_stable_audio', format: 'wav' }),
    );
  });
});
