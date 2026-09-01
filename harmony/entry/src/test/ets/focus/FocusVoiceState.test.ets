import { describe, expect, it } from '@ohos/hypium';
import { FocusVoiceEventReducer, FocusVoiceState } from '../../../main/ets/features/focus/FocusVoiceState';

export default function focusVoiceStateTest(): void {
  describe('FocusVoiceEventReducer', () => {
    it('maps relay state and barge-in events to the expected voice phase', 0, () => {
      let state: FocusVoiceState = FocusVoiceEventReducer.initial();
      state = FocusVoiceEventReducer.reduce(state, '{"type":"state","state":"speaking"}');
      expect(state.phase).assertEqual('SPEAKING');
      state = FocusVoiceEventReducer.reduce(state, '{"type":"user_speech_started"}');
      expect(state.phase).assertEqual('LISTENING');
      expect(state.answer).assertEqual('');
    });

    it('keeps cumulative transcription and answer deltas available to the UI', 0, () => {
      let state: FocusVoiceState = FocusVoiceEventReducer.initial();
      state = FocusVoiceEventReducer.reduce(state, '{"type":"user_transcript_delta","text":"我想"}');
      state = FocusVoiceEventReducer.reduce(state, '{"type":"user_transcript_delta","text":"我想开始"}');
      state = FocusVoiceEventReducer.reduce(state, '{"type":"ai_text_delta","text":"先写"}');
      state = FocusVoiceEventReducer.reduce(state, '{"type":"ai_text_delta","text":"先写第一题"}');
      expect(state.transcript).assertEqual('我想开始');
      expect(state.answer).assertEqual('先写第一题');
    });

    it('surfaces a backend error without losing the last transcript', 0, () => {
      let state: FocusVoiceState = FocusVoiceEventReducer.initial();
      state = FocusVoiceEventReducer.reduce(state, '{"type":"user_transcript_done","text":"帮我规划"}');
      state = FocusVoiceEventReducer.reduce(state, '{"type":"error","message":"服务暂不可用"}');
      expect(state.phase).assertEqual('ERROR');
      expect(state.transcript).assertEqual('帮我规划');
      expect(state.message).assertEqual('服务暂不可用');
    });
  });
}
