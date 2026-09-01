import { webSocket } from '@kit.NetworkKit';
import { audio } from '@kit.AudioKit';
import { BusinessError } from '@kit.BasicServicesKit';
import { FocusVoiceEventReducer, FocusVoiceState } from '../features/focus/FocusVoiceState';

export type FocusVoiceEventHandler = (event: FocusVoiceState) => void;

/** Native Harmony transport for the same PCM/WebSocket relay used by Android. */
export class FocusRealtimeVoiceClient {
  private socket?: webSocket.WebSocket = undefined;
  private capturer?: audio.AudioCapturer = undefined;
  private renderer?: audio.AudioRenderer = undefined;
  private currentState: FocusVoiceState = FocusVoiceEventReducer.initial();
  private readonly onState: FocusVoiceEventHandler;
  private readonly onClosed: () => void;
  private readHandler: (data: ArrayBuffer) => void = (data: ArrayBuffer): void => {
    const socket = this.socket;
    if (socket !== undefined) socket.send(data).catch(() => {});
  };

  constructor(onState: FocusVoiceEventHandler, onClosed: () => void = () => {}) {
    this.onState = onState;
    this.onClosed = onClosed;
  }

  state(): FocusVoiceState { return this.currentState; }

  async connect(url: string): Promise<void> {
    await this.close(false);
    this.currentState = FocusVoiceEventReducer.connecting();
    this.onState(this.currentState);
    const socket: webSocket.WebSocket = webSocket.createWebSocket();
    this.socket = socket;
    socket.on('open', async () => {
      try {
        await this.startAudio();
        this.currentState = {
          phase: 'LISTENING',
          message: '正在听你说…',
          transcript: this.currentState.transcript,
          answer: this.currentState.answer
        };
        this.onState(this.currentState);
      } catch (_) {
        this.emitError('麦克风初始化失败，请检查系统权限');
      }
    });
    socket.on('message', (_error: BusinessError, data: string | ArrayBuffer) => {
      if (typeof data === 'string') {
        this.currentState = FocusVoiceEventReducer.reduce(this.currentState, data);
        this.onState(this.currentState);
      } else {
        this.playAudio(data);
      }
    });
    socket.on('error', () => this.emitError('实时语音连接失败，请稍后重试'));
    socket.on('close', () => {
      this.stopAudio();
      this.socket = undefined;
      this.onClosed();
    });
    const connected: boolean = await socket.connect(url);
    if (!connected) this.emitError('实时语音连接失败，请稍后重试');
  }

  async stop(): Promise<void> {
    const socket = this.socket;
    if (socket !== undefined) {
      try { await socket.send(JSON.stringify({ type: 'stop' })); } catch (_) {}
    }
    await this.close(true);
  }

  async interrupt(): Promise<void> {
    const socket = this.socket;
    if (socket !== undefined) {
      try { await socket.send(JSON.stringify({ type: 'response.cancel' })); } catch (_) {}
    }
  }

  private emitError(message: string): void {
    this.currentState = {
      phase: 'ERROR',
      message: message,
      transcript: this.currentState.transcript,
      answer: this.currentState.answer
    };
    this.onState(this.currentState);
  }

  private async startAudio(): Promise<void> {
    const capturerOptions: audio.AudioCapturerOptions = {
      streamInfo: {
        samplingRate: audio.AudioSamplingRate.SAMPLE_RATE_16000,
        channels: audio.AudioChannel.CHANNEL_1,
        sampleFormat: audio.AudioSampleFormat.SAMPLE_FORMAT_S16LE,
        encodingType: audio.AudioEncodingType.ENCODING_TYPE_RAW
      },
      capturerInfo: {
        source: audio.SourceType.SOURCE_TYPE_VOICE_RECOGNITION,
        capturerFlags: 0
      }
    };
    const rendererOptions: audio.AudioRendererOptions = {
      streamInfo: {
        samplingRate: audio.AudioSamplingRate.SAMPLE_RATE_24000,
        channels: audio.AudioChannel.CHANNEL_1,
        sampleFormat: audio.AudioSampleFormat.SAMPLE_FORMAT_S16LE,
        encodingType: audio.AudioEncodingType.ENCODING_TYPE_RAW
      },
      rendererInfo: {
        usage: audio.StreamUsage.STREAM_USAGE_VOICE_COMMUNICATION,
        rendererFlags: 0
      }
    };
    this.capturer = await audio.createAudioCapturer(capturerOptions);
    this.renderer = await audio.createAudioRenderer(rendererOptions);
    this.capturer.on('readData', this.readHandler);
    await this.renderer.start();
    await this.capturer.start();
  }

  private playAudio(data: ArrayBuffer): void {
    const renderer = this.renderer;
    if (renderer !== undefined && renderer.state === audio.AudioState.STATE_RUNNING) {
      renderer.write(data).catch(() => {});
    }
  }

  private stopAudio(): void {
    const capturer = this.capturer;
    const renderer = this.renderer;
    this.capturer = undefined;
    this.renderer = undefined;
    if (capturer !== undefined) {
      try { capturer.off('readData', this.readHandler); } catch (_) {}
      capturer.stop().catch(() => {});
      capturer.release().catch(() => {});
    }
    if (renderer !== undefined) {
      renderer.stop().catch(() => {});
      renderer.release().catch(() => {});
    }
  }

  private async close(notify: boolean): Promise<void> {
    this.stopAudio();
    const socket = this.socket;
    this.socket = undefined;
    if (socket !== undefined) {
      try { await socket.close({ code: 1000, reason: 'focus voice closed' }); } catch (_) {}
    }
    if (notify) this.onClosed();
  }
}
