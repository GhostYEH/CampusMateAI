import { mindSporeLite } from '@kit.MindSporeLiteKit';
import { resourceManager } from '@kit.LocalizationKit';
import {
  BehaviorReminderTracker,
  BehaviorSessionSummary,
  BehaviorSessionSummaryTracker,
  BehaviorV34Decision,
  BehaviorV34Label,
  BehaviorV34Result
} from './BehaviorV34Decision';
import {
  FocusAssistProvider,
  FocusAssistSignal,
  FocusAssistStatus,
  PersonBox,
  RgbaBehaviorFrame
} from './FocusAssistProvider';

export class BehaviorRoiPreprocessor {
  private static readonly SIZE: number = 224;
  private static readonly MEAN: number[] = [0.485, 0.456, 0.406];
  private static readonly STD: number[] = [0.229, 0.224, 0.225];

  static toNchw(frame: RgbaBehaviorFrame): Float32Array | undefined {
    if (frame.width <= 0 || frame.height <= 0 || frame.pixels.length < frame.width * frame.height * 4) return undefined;
    const box: PersonBox | undefined = BehaviorRoiPreprocessor.expandedBox(frame.personBox, frame.width, frame.height);
    if (box === undefined) return undefined;
    const output: Float32Array = new Float32Array(3 * BehaviorRoiPreprocessor.SIZE * BehaviorRoiPreprocessor.SIZE);
    const roiWidth: number = box.right - box.left;
    const roiHeight: number = box.bottom - box.top;
    const plane: number = BehaviorRoiPreprocessor.SIZE * BehaviorRoiPreprocessor.SIZE;
    for (let y: number = 0; y < BehaviorRoiPreprocessor.SIZE; y++) {
      const sourceY: number = Math.min(frame.height - 1, Math.max(0,
        box.top + (y + 0.5) * roiHeight / BehaviorRoiPreprocessor.SIZE - 0.5));
      const y0: number = Math.floor(sourceY);
      const y1: number = Math.min(frame.height - 1, y0 + 1);
      const yWeight: number = sourceY - y0;
      for (let x: number = 0; x < BehaviorRoiPreprocessor.SIZE; x++) {
        const sourceX: number = Math.min(frame.width - 1, Math.max(0,
          box.left + (x + 0.5) * roiWidth / BehaviorRoiPreprocessor.SIZE - 0.5));
        const x0: number = Math.floor(sourceX);
        const x1: number = Math.min(frame.width - 1, x0 + 1);
        const xWeight: number = sourceX - x0;
        const topLeft: number = (y0 * frame.width + x0) * 4;
        const topRight: number = (y0 * frame.width + x1) * 4;
        const bottomLeft: number = (y1 * frame.width + x0) * 4;
        const bottomRight: number = (y1 * frame.width + x1) * 4;
        const target: number = y * BehaviorRoiPreprocessor.SIZE + x;
        for (let channel: number = 0; channel < 3; channel++) {
          const top: number = frame.pixels[topLeft + channel] * (1 - xWeight) +
            frame.pixels[topRight + channel] * xWeight;
          const bottom: number = frame.pixels[bottomLeft + channel] * (1 - xWeight) +
            frame.pixels[bottomRight + channel] * xWeight;
          const pixel: number = top * (1 - yWeight) + bottom * yWeight;
          const normalized: number = (pixel / 255.0 - BehaviorRoiPreprocessor.MEAN[channel]) /
            BehaviorRoiPreprocessor.STD[channel];
          output[channel * plane + target] = normalized;
        }
      }
    }
    return output;
  }

  private static expandedBox(input: PersonBox, width: number, height: number): PersonBox | undefined {
    const rawWidth: number = input.right - input.left;
    const rawHeight: number = input.bottom - input.top;
    if (rawWidth < 2 || rawHeight < 2) return undefined;
    const extraX: number = rawWidth * 0.10;
    const extraY: number = rawHeight * 0.10;
    const box: PersonBox = {
      left: Math.max(0, input.left - extraX),
      top: Math.max(0, input.top - extraY),
      right: Math.min(width, input.right + extraX),
      bottom: Math.min(height, input.bottom + extraY)
    };
    return box.right - box.left >= 2 && box.bottom - box.top >= 2 ? box : undefined;
  }
}

export class BehaviorTemporalFrameBuffer {
  private static readonly FRAME_COUNT: number = 8;
  private static readonly FRAME_SIZE: number = 3 * 224 * 224;
  private readonly frames: Float32Array[] = [];

  push(frame: Float32Array): void {
    if (frame.length !== BehaviorTemporalFrameBuffer.FRAME_SIZE) return;
    this.frames.push(frame.slice());
    while (this.frames.length > BehaviorTemporalFrameBuffer.FRAME_COUNT) {
      this.frames.shift();
    }
  }

  snapshot(): Float32Array[] {
    return this.frames.map((frame: Float32Array) => frame.slice());
  }

  toModelInput(): Float32Array | undefined {
    if (this.frames.length !== BehaviorTemporalFrameBuffer.FRAME_COUNT) return undefined;
    const output: Float32Array = new Float32Array(
      BehaviorTemporalFrameBuffer.FRAME_COUNT * BehaviorTemporalFrameBuffer.FRAME_SIZE
    );
    for (let index: number = 0; index < this.frames.length; index++) {
      output.set(this.frames[index], index * BehaviorTemporalFrameBuffer.FRAME_SIZE);
    }
    return output;
  }

  reset(): void {
    this.frames.length = 0;
  }
}

export class MindSporeBehaviorProvider implements FocusAssistProvider {
  private readonly manager: resourceManager.ResourceManager;
  private model: mindSporeLite.Model | null = null;
  private providerStatus: FocusAssistStatus = FocusAssistStatus.UNAVAILABLE;
  private providerDetail: string = 'V3.4 本地模型尚未加载';
  private signal: FocusAssistSignal | undefined = undefined;
  private readonly reminderTracker: BehaviorReminderTracker = new BehaviorReminderTracker();
  private readonly sessionSummaryTracker: BehaviorSessionSummaryTracker = new BehaviorSessionSummaryTracker();
  private activeRun: boolean = false;

  constructor(manager: resourceManager.ResourceManager) {
    this.manager = manager;
  }

  available(): boolean { return this.model !== null && this.providerStatus === FocusAssistStatus.RUNNING; }
  status(): FocusAssistStatus { return this.providerStatus; }
  latestSignal(): FocusAssistSignal | undefined { return this.signal; }
  currentReminder(): string { return this.reminderTracker.current(); }
  sessionSummary(): BehaviorSessionSummary | undefined {
    if (!this.activeRun) return undefined;
    return this.sessionSummaryTracker.summary(Date.now(), 'V3.4');
  }
  detail(): string { return this.providerDetail; }

  async start(): Promise<void> {
    this.activeRun = true;
    this.sessionSummaryTracker.reset(Date.now());
    if (this.model !== null) {
      if (this.providerStatus !== FocusAssistStatus.RUNNING) {
        this.providerStatus = FocusAssistStatus.UNAVAILABLE;
        this.providerDetail = 'V3.4 模型已就绪；等待本地相机人体 ROI 管线';
      }
      return;
    }
    try {
      const bytes: Uint8Array = await this.manager.getRawFileContent('models/behavior/campusmate_behavior_v34.ms');
      const modelBuffer: ArrayBuffer = new ArrayBuffer(bytes.byteLength);
      new Uint8Array(modelBuffer).set(bytes);
      const loaded: mindSporeLite.Model = await mindSporeLite.loadModelFromBuffer(modelBuffer);
      const inputs: mindSporeLite.MSTensor[] = loaded.getInputs();
      if (inputs.length !== 1 || inputs[0].shape.length !== 4 || inputs[0].elementNum !== 3 * 224 * 224) {
        throw new Error('V3.4 input contract mismatch');
      }
      this.model = loaded;
      this.providerStatus = FocusAssistStatus.UNAVAILABLE;
      this.providerDetail = 'V3.4 模型已就绪；等待本地相机人体 ROI 管线';
    } catch (error) {
      this.model = null;
      this.providerStatus = FocusAssistStatus.ERROR;
      this.providerDetail = 'V3.4 本地模型不可用，已停止行为提醒';
    }
  }

  async stop(): Promise<void> {
    this.activeRun = false;
    this.signal = undefined;
    this.reminderTracker.reset();
    this.providerStatus = FocusAssistStatus.UNAVAILABLE;
  }

  async analyze(frame: RgbaBehaviorFrame): Promise<FocusAssistSignal | undefined> {
    if (this.model === null) {
      this.providerStatus = FocusAssistStatus.UNAVAILABLE;
      this.providerDetail = '缺少可用模型，无法进行本地行为识别';
      return undefined;
    }
    const inputData: Float32Array | undefined = BehaviorRoiPreprocessor.toNchw(frame);
    if (inputData === undefined) {
      this.providerStatus = FocusAssistStatus.UNAVAILABLE;
      this.providerDetail = '未获得有效人体框，暂不进行行为识别';
      return undefined;
    }
    try {
      this.providerStatus = FocusAssistStatus.RUNNING;
      const inputs: mindSporeLite.MSTensor[] = this.model.getInputs();
      inputs[0].setData(inputData.buffer);
      const outputs: mindSporeLite.MSTensor[] = await this.model.predict(inputs);
      if (outputs.length !== 1 || outputs[0].elementNum !== 4) throw new Error('V3.4 output contract mismatch');
      const raw: Float32Array = new Float32Array(outputs[0].getData());
      const logits: number[] = [raw[0], raw[1], raw[2], raw[3]];
      const result: BehaviorV34Result = BehaviorV34Decision.decode(logits);
      const next: FocusAssistSignal = {
        label: result.label,
        confidence: result.confidence,
        isStable: result.isStable,
        timestamp: frame.timestamp,
        modelVersion: 'V3.4'
      };
      this.signal = next;
      const reminder: string = this.reminderTracker.process(result, frame.timestamp);
      this.sessionSummaryTracker.process(result, frame.timestamp, reminder);
      this.providerStatus = FocusAssistStatus.RUNNING;
      this.providerDetail = result.label === BehaviorV34Label.CONTINUE_OBSERVING ? '结果不可靠，继续观察' : 'V3.4 正在本地识别';
      return next;
    } catch (error) {
      this.providerStatus = FocusAssistStatus.ERROR;
      this.providerDetail = '本帧推理失败，未触发行为提醒';
      return undefined;
    }
  }
}
