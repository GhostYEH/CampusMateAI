import { describe, expect, it } from '@ohos/hypium';
import { FocusRealtimeVoiceRepository } from '../../../main/ets/repository/FocusRealtimeVoiceRepository';

export default function focusRealtimeVoiceRepositoryTest(): void {
  describe('FocusRealtimeVoiceRepository', () => {
    it('converts a relative voice path into an authenticated websocket endpoint', 0, () => {
      const url = FocusRealtimeVoiceRepository.authenticatedWebSocketUrl(
        'https://api.example.com/api/v1/', 'focus/realtime-voice/ws/session-1', 'token value');
      expect(url).assertEqual('wss://api.example.com/api/v1/focus/realtime-voice/ws/session-1?access_token=token%20value');
    });

    it('keeps an existing websocket scheme and query delimiter intact', 0, () => {
      const url = FocusRealtimeVoiceRepository.authenticatedWebSocketUrl(
        'https://api.example.com/api/v1', 'wss://voice.example.com/ws/id?lang=zh', 'abc');
      expect(url).assertEqual('wss://voice.example.com/ws/id?lang=zh&access_token=abc');
    });
  });
}
