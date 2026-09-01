import { http } from '@kit.NetworkKit';
import { ApiClient } from '../data/ApiClient';
import { FocusRealtimeVoiceSession, FocusRealtimeVoiceStop } from '../data/Models';

export class FocusRealtimeVoiceRepository {
  private readonly client: ApiClient;
  private readonly accessToken: () => string;

  constructor(client: ApiClient, accessToken: () => string) {
    this.client = client;
    this.accessToken = accessToken;
  }

  async createSession(): Promise<FocusRealtimeVoiceSession> {
    return this.client.request<FocusRealtimeVoiceSession>(http.RequestMethod.POST, 'focus/realtime-voice/sessions');
  }

  async stopSession(sessionId: string): Promise<FocusRealtimeVoiceStop> {
    return this.client.request<FocusRealtimeVoiceStop>(http.RequestMethod.DELETE, `focus/realtime-voice/sessions/${sessionId}`);
  }

  websocketUrl(path: string): string {
    return FocusRealtimeVoiceRepository.authenticatedWebSocketUrl(
      this.client.normalizedUrl(''), path, this.accessToken());
  }

  static authenticatedWebSocketUrl(baseUrl: string, path: string, accessToken: string): string {
    const base: string = baseUrl.replace(/\/$/, '');
    let target: string = path.trim();
    if (!target.startsWith('ws://') && !target.startsWith('wss://')) {
      target = `${base}/${target.replace(/^\//, '')}`;
    }
    target = target.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:');
    const queryDelimiter: string = target.includes('?') ? '&' : '?';
    return `${target}${queryDelimiter}access_token=${encodeURIComponent(accessToken)}`;
  }
}
