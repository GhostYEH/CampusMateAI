import { describe, it, expect } from '@ohos/hypium';
import { ExpressionRecognitionProvider } from '../../../main/ets/service/ExpressionRecognitionProvider';
import {
  ExpressionCameraActivationPolicy,
  ExpressionRecognitionService
} from '../../../main/ets/service/ExpressionRecognitionService';
import { StableExpressionSignal } from '../../../main/ets/service/ExpressionSignalProcessor';

class DeferredExpressionProvider implements ExpressionRecognitionProvider {
  private startResolver: (() => void) | undefined = undefined;
  private startGate: Promise<void>;
  running: boolean = false;
  startCalls: number = 0;
  stopCalls: number = 0;

  constructor() {
    this.startGate = new Promise<void>((resolve: () => void): void => {
      this.startResolver = resolve;
    });
  }

  available(): boolean { return this.running; }
  latestSignal(): StableExpressionSignal | undefined { return undefined; }
  detail(): string { return this.running ? 'running' : 'stopped'; }

  async start(): Promise<void> {
    this.startCalls += 1;
    await this.startGate;
    this.running = true;
  }

  async stop(): Promise<void> {
    this.stopCalls += 1;
    this.running = false;
  }

  completeStart(): void {
    this.startResolver?.();
  }
}

export default function expressionRecognitionServiceTest(): void {
  describe('ExpressionRecognitionService lifecycle', () => {
    it('allows camera startup only for a consented visible signed-in CPM tab', 0, () => {
      expect(ExpressionCameraActivationPolicy.shouldRun(true, true, true, 3)).assertTrue();
      expect(ExpressionCameraActivationPolicy.shouldRun(false, true, true, 3)).assertFalse();
      expect(ExpressionCameraActivationPolicy.shouldRun(true, false, true, 3)).assertFalse();
      expect(ExpressionCameraActivationPolicy.shouldRun(true, true, false, 3)).assertFalse();
      expect(ExpressionCameraActivationPolicy.shouldRun(true, true, true, 2)).assertFalse();
    });

    it('lets stop invalidate and await an in-flight start', 0, async () => {
      const provider: DeferredExpressionProvider = new DeferredExpressionProvider();
      const service: ExpressionRecognitionService = new ExpressionRecognitionService(provider);
      const startTask: Promise<void> = service.start();
      await Promise.resolve();
      const stopTask: Promise<void> = service.stop();
      provider.completeStart();
      await Promise.all([startTask, stopTask]);

      expect(provider.startCalls).assertEqual(1);
      expect(provider.stopCalls).assertEqual(1);
      expect(provider.running).assertFalse();
      expect(service.available()).assertFalse();
    });

    it('keeps repeated stop idempotent after shutdown', 0, async () => {
      const provider: DeferredExpressionProvider = new DeferredExpressionProvider();
      const service: ExpressionRecognitionService = new ExpressionRecognitionService(provider);
      provider.completeStart();
      await service.start();
      await Promise.all([service.stop(), service.stop()]);
      await service.stop();

      expect(provider.stopCalls).assertEqual(1);
      expect(provider.running).assertFalse();
    });
  });
}
