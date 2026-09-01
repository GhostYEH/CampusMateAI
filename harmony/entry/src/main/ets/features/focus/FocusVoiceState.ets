export type FocusVoicePhase = 'IDLE' | 'CONNECTING' | 'LISTENING' | 'SPEAKING' | 'ERROR';

export interface FocusVoiceState {
  phase: FocusVoicePhase;
  message: string;
  transcript: string;
  answer: string;
}

interface VoiceRelayEvent {
  type?: string;
  state?: string;
  text?: string;
  message?: string;
}

export class FocusVoiceEventReducer {
  static initial(): FocusVoiceState {
    return { phase: 'IDLE', message: '点击麦克风，和 CampusMate 实时对话', transcript: '', answer: '' };
  }

  static connecting(): FocusVoiceState {
    return { phase: 'CONNECTING', message: '正在连接实时语音…', transcript: '', answer: '' };
  }

  static reduce(current: FocusVoiceState, raw: string): FocusVoiceState {
    let event: VoiceRelayEvent;
    try {
      event = JSON.parse(raw) as VoiceRelayEvent;
    } catch (_) {
      return current;
    }
    const text: string = event.text ?? '';
    if (event.type === 'state') {
      if (event.state === 'speaking') return { phase: 'SPEAKING', message: 'CampusMate 正在回答…', transcript: current.transcript, answer: current.answer };
      if (event.state === 'listening') return { phase: 'LISTENING', message: '正在听你说…', transcript: current.transcript, answer: current.answer };
      return current;
    }
    if (event.type === 'user_speech_started') {
      return { phase: 'LISTENING', message: '正在听你说…', transcript: current.transcript, answer: '' };
    }
    if (event.type === 'user_transcript_delta' || event.type === 'user_transcript_done') {
      return { phase: current.phase, message: current.message, transcript: text.length > 0 ? text : current.transcript, answer: current.answer };
    }
    if (event.type === 'ai_text_delta' || event.type === 'ai_text_done') {
      return { phase: current.phase, message: current.message, transcript: current.transcript, answer: text.length > 0 ? text : current.answer };
    }
    if (event.type === 'error') {
      return { phase: 'ERROR', message: event.message ?? '实时语音服务暂不可用', transcript: current.transcript, answer: current.answer };
    }
    if (event.type === 'session_closed') return FocusVoiceEventReducer.initial();
    return current;
  }
}
