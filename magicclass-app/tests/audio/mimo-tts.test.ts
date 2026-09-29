import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { generateTTS, TTSInvalidResponseError, TTSRateLimitError } from '@/lib/audio/tts-providers';
import { DEFAULT_TTS_VOICES, TTS_PROVIDERS } from '@/lib/audio/constants';

const mockFetch = vi.hoisted(() => vi.fn() as Mock);
vi.mock('undici', async (importOriginal) => {
  const actual = await importOriginal<typeof import('undici')>();
  return { ...actual, fetch: mockFetch };
});

function wav(): Buffer {
  const bytes = Buffer.alloc(48);
  bytes.write('RIFF', 0, 'ascii');
  bytes.write('WAVE', 8, 'ascii');
  return bytes;
}

describe('MiMo V2.5 TTS', () => {
  beforeEach(() => mockFetch.mockReset());

  it('offers the documented voices before classroom entry', () => {
    expect(TTS_PROVIDERS['mimo-tts'].voices.map((voice) => voice.id)).toEqual([
      '冰糖', '茉莉', '苏打', '白桦', 'Mia', 'Chloe', 'Milo', 'Dean',
    ]);
    expect(DEFAULT_TTS_VOICES['mimo-tts']).toBe('苏打');
  });

  it('sends teacher narration in the assistant message and plays the selected voice', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ choices: [{ message: { audio: { data: wav().toString('base64') } } }] }),
    });

    const result = await generateTTS(
      { providerId: 'mimo-tts', modelId: 'mimo-v2.5-tts', apiKey: 'test-key', voice: '茉莉', speed: 0.8 },
      '看这张幻灯片，我们先理解函数的定义。',
    );

    expect(mockFetch).toHaveBeenCalledWith(
      'https://api.xiaomimimo.com/v1/chat/completions',
      expect.objectContaining({ method: 'POST' }),
    );
    const request = mockFetch.mock.calls[0][1];
    const body = JSON.parse(request.body);
    expect(request.headers.Authorization).toBe('Bearer test-key');
    expect(body).toMatchObject({
      model: 'mimo-v2.5-tts',
      messages: [
        { role: 'user', content: expect.stringContaining('语速稍慢') },
        { role: 'assistant', content: '看这张幻灯片，我们先理解函数的定义。' },
      ],
      audio: { format: 'wav', voice: '茉莉' },
    });
    expect(body.speed).toBeUndefined();
    expect(result.format).toBe('wav');
    expect(Buffer.from(result.audio)).toEqual(wav());
  });

  it('rejects malformed provider audio without creating a playback asset', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ choices: [{ message: { audio: { data: Buffer.from('not audio').toString('base64') } } }] }),
    });
    await expect(generateTTS({ providerId: 'mimo-tts', apiKey: 'test-key', voice: '苏打' }, '讲解')).rejects.toThrow(
      TTSInvalidResponseError,
    );
  });

  it('keeps upstream error bodies private and classifies rate limits', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 429 });
    await expect(generateTTS({ providerId: 'mimo-tts', apiKey: 'test-key', voice: '苏打' }, '讲解')).rejects.toThrow(
      TTSRateLimitError,
    );
  });
});
