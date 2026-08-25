import { StableExpressionSignal } from './ExpressionSignalProcessor';

export interface ExpressionRecognitionProvider {
  available(): boolean;
  start(): Promise<void>;
  stop(): Promise<void>;
  latestSignal(): StableExpressionSignal | undefined;
  detail(): string;
}

/** Safe default until a HarmonyOS API 24 camera/model provider is verified. */
export class UnavailableExpressionProvider implements ExpressionRecognitionProvider {
  available(): boolean { return false; }
  async start(): Promise<void> { return; }
  async stop(): Promise<void> { return; }
  latestSignal(): StableExpressionSignal | undefined { return undefined; }
  detail(): string { return '当前设备暂不支持本地表情模型，聊天不会上传相机画面'; }
}
