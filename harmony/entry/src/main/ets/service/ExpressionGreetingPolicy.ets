import { StableExpressionSignal } from './ExpressionSignalProcessor';

/** Uses uncertainty-aware wording because a facial expression is not a mental-health diagnosis. */
export class ExpressionGreetingPolicy {
  static greeting(signal: StableExpressionSignal | undefined): string {
    if (signal === undefined) return '你好，我是 CPM 校园助手。今天有什么想聊的？';
    if (signal.label === 'sad') return '看起来你可能有点难过。别难过，也别一个人扛着，我在这里陪你。';
    if (signal.label === 'angry' || signal.label === 'disgust') {
      return '感觉你现在可能有些烦闷。先缓一缓，我们可以一起把事情理清楚。';
    }
    if (signal.label === 'fear') return '看起来你可能有些紧张。没关系，我们慢慢来，我会陪你一起想办法。';
    if (signal.label === 'happy' || signal.label === 'surprise') return '看起来你今天状态不错！很高兴见到你，有什么想和我分享的？';
    return '你好，我是 CPM 校园助手。今天感觉怎么样？我会认真听你说。';
  }
}
