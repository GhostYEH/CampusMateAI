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
  BehaviorHybridPolicy,
  BehaviorTsmContract,
  BehaviorTsmResult
} from './BehaviorHybridPolicy';
import {
  FocusAssistProvider,
  FocusAssistSignal,
  FocusAssistStatus,
  RgbaBehaviorFrame
} from './FocusAssistProvider';
import { PersonBox } from './FocusCameraContract';
import { BehaviorModelSelection, BehaviorRuntimeModel } from './BehaviorModelSelection';
import { BehaviorPredictionTemporalSmoother } from './BehaviorPredictionTemporalSmoother';
import {
  BehaviorSignalProcessor,
  StableBehaviorEvent
} from './BehaviorSignalProcessor';
import {
  BehaviorDisplayState,
  BehaviorDisplayStates,
  BehaviorDisplayStateKind,
  LearningContinuityState,
  LearningContinuityStateMachine
} from './LearningContinuityStateMachine';
import { PresenceState, PresenceStateMachine } from './PresenceStateMachine';

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

/** Complete-frame RGB preprocessing for TSM. Only the resized CHW tensor is retained. */
export class BehaviorFullFramePreprocessor {
  static readonly SIZE: number = 224;
  static readonly FRAME_SIZE: number = 3 * BehaviorFullFramePreprocessor.SIZE *
    BehaviorFullFramePreprocessor.SIZE;

  static toChw(frame: RgbaBehaviorFrame): Float32Array | undefined {
    if (frame.width <= 0 || frame.height <= 0 ||
      frame.pixels.length < frame.width * frame.height * 4) return undefined;
    const output: Float32Array = new Float32Array(BehaviorFullFramePreprocessor.FRAME_SIZE);
    const plane: number = BehaviorFullFramePreprocessor.SIZE * BehaviorFullFramePreprocessor.SIZE;
    for (let y: number = 0; y < BehaviorFullFramePreprocessor.SIZE; y++) {
      const sourceY: number = Math.min(frame.height - 1, Math.max(0,
        (y + 0.5) * frame.height / BehaviorFullFramePreprocessor.SIZE - 0.5));
      const y0: number = Math.floor(sourceY);
      const y1: number = Math.min(frame.height - 1, y0 + 1);
      const yWeight: number = sourceY - y0;
      for (let x: number = 0; x < BehaviorFullFramePreprocessor.SIZE; x++) {
        const sourceX: number = Math.min(frame.width - 1, Math.max(0,
          (x + 0.5) * frame.width / BehaviorFullFramePreprocessor.SIZE - 0.5));
        const x0: number = Math.floor(sourceX);
        const x1: number = Math.min(frame.width - 1, x0 + 1);
        const xWeight: number = sourceX - x0;
        const topLeft: number = (y0 * frame.width + x0) * 4;
        const topRight: number = (y0 * frame.width + x1) * 4;
        const bottomLeft: number = (y1 * frame.width + x0) * 4;
        const bottomRight: number = (y1 * frame.width + x1) * 4;
        const target: number = y * BehaviorFullFramePreprocessor.SIZE + x;
        for (let channel: number = 0; channel < 3; channel++) {
          const top: number = frame.pixels[topLeft + channel] * (1 - xWeight) +
            frame.pixels[topRight + channel] * xWeight;
          const bottom: number = frame.pixels[bottomLeft + channel] * (1 - xWeight) +
            frame.pixels[bottomRight + channel] * xWeight;
          output[channel * plane + target] = top * (1 - yWeight) + bottom * yWeight;
        }
      }
    }
    return output;
  }
}

export class BehaviorV34OutputContract {
  private static readonly LOGIT_COUNT: number = 4;

  static decode(logits: number[]): BehaviorV34Result | undefined {
    if (logits.length !== BehaviorV34OutputContract.LOGIT_COUNT) return undefined;
    for (let index: number = 0; index < logits.length; index++) {
      if (!Number.isFinite(logits[index])) return undefined;
    }
    const result: BehaviorV34Result = BehaviorV34Decision.decode(logits);
    if (result.probabilities.length !== BehaviorV34OutputContract.LOGIT_COUNT) return undefined;
    let sum: number = 0;
    for (let index: number = 0; index < result.probabilities.length; index++) {
      const probability: number = result.probabilities[index];
      if (!Number.isFinite(probability) || probability < 0) return undefined;
      sum += probability;
    }
    return Number.isFinite(sum) && sum > 0 ? result : undefined;
  }
}

export class BehaviorProviderRunToken {
  private generation: number = 0;
  private active: boolean = false;

  begin(): number {
    this.generation += 1;
    this.active = true;
    return this.generation;
  }

  invalidate(): void {
    this.generation += 1;
    this.active = false;
  }

  isCurrent(generation: number): boolean {
    return this.active && generation === this.generation;
  }
}

export class BehaviorProviderPresentation {
  static detail(temporalDegraded: boolean, label: BehaviorV34Label,
    hasTemporalEvidence: boolean = false): string {
    if (temporalDegraded) return 'TSM V4 不可用，V3.4 正在本地识别';
    if (label === BehaviorV34Label.CONTINUE_OBSERVING) return '结果不可靠，继续观察';
    return hasTemporalEvidence ? 'V3.4 + TSM V4 正在本地识别' : 'V3.4 正在本地识别';
  }

  static modelVersion(hasTemporalEvidence: boolean): string {
    return hasTemporalEvidence ? 'V3.4+TSM-V4' : 'V3.4';
  }

  static readyDetail(temporalDegraded: boolean): string {
    return temporalDegraded ?
      'V3.4 模型已就绪；TSM V4 不可用，使用降级行为识别' :
      'V3.4 与 TSM V4 模型已就绪；等待本地相机人体 ROI 管线';
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

  size(): number {
    return this.frames.length;
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
  private static readonly V34_MODEL_PATH: string = 'models/behavior/campusmate_behavior_v34.ms';
  private static readonly V32_MODEL_PATH: string = 'models/behavior/campusmate_visible_study_v32.ms';
  private static readonly TSM_MODEL_PATH: string = 'models/behavior/campusmate_tsm_mobilenetv2_v4.ms';
  private readonly manager: resourceManager.ResourceManager;
  private model: mindSporeLite.Model | null = null;
  private v32Model: mindSporeLite.Model | null = null;
  private temporalModel: mindSporeLite.Model | null = null;
  private providerStatus: FocusAssistStatus = FocusAssistStatus.UNAVAILABLE;
  private providerDetail: string = 'V3.4 本地模型尚未加载';
  private signal: FocusAssistSignal | undefined = undefined;
  private readonly reminderTracker: BehaviorReminderTracker = new BehaviorReminderTracker();
  private readonly sessionSummaryTracker: BehaviorSessionSummaryTracker = new BehaviorSessionSummaryTracker();
  private sessionSummaryInitialized: boolean = false;
  private readonly temporalFrames: BehaviorTemporalFrameBuffer = new BehaviorTemporalFrameBuffer();
  private previousSingleTop: BehaviorV34Label | undefined = undefined;
  private lastTemporalAtMs: number = 0;
  private cachedTemporal: BehaviorTsmResult | undefined = undefined;
  private computerConfirmationCount: number = 0;
  private temporalDegraded: boolean = false;
  private readonly runToken: BehaviorProviderRunToken = new BehaviorProviderRunToken();
  private activeRun: number = 0;
  private readonly temporalSmoother: BehaviorPredictionTemporalSmoother = new BehaviorPredictionTemporalSmoother(0.35);
  private readonly signalProcessor: BehaviorSignalProcessor = new BehaviorSignalProcessor();
  private readonly continuityStateMachine: LearningContinuityStateMachine = new LearningContinuityStateMachine();
  private readonly presenceStateMachine: PresenceStateMachine = new PresenceStateMachine();
  private currentDisplayState: BehaviorDisplayState = BehaviorDisplayStates.observing();
  private currentContinuityState: LearningContinuityState = LearningContinuityState.OBSERVING;
  private currentPresenceState: PresenceState = PresenceState.OBSERVING;

  constructor(manager: resourceManager.ResourceManager) {
    this.manager = manager;
  }

  available(): boolean { return this.model !== null && this.providerStatus === FocusAssistStatus.RUNNING; }
  status(): FocusAssistStatus { return this.providerStatus; }
  latestSignal(): FocusAssistSignal | undefined { return this.signal; }
  currentReminder(): string { return this.reminderTracker.current(); }
  sessionSummary(): BehaviorSessionSummary | undefined {
    if (!this.sessionSummaryInitialized) return undefined;
    return this.sessionSummaryTracker.summary(
      Date.now(), BehaviorProviderPresentation.modelVersion(this.cachedTemporal !== undefined));
  }
  resetSessionSummary(startedAt: number = Date.now()): void {
    this.sessionSummaryTracker.reset(startedAt);
    this.sessionSummaryInitialized = true;
  }
  recordAbsence(): void {
    if (this.activeRun !== 0 && this.sessionSummaryInitialized) {
      this.sessionSummaryTracker.recordAbsence();
    }
  }
  detail(): string { return this.providerDetail; }

  async start(): Promise<void> {
    const run: number = this.runToken.begin();
    this.activeRun = run;
    this.clearProductState();
    if (!this.sessionSummaryInitialized) {
      this.resetSessionSummary();
    } else {
      this.sessionSummaryTracker.resume(Date.now());
    }
    if (this.model !== null) {
      this.providerStatus = FocusAssistStatus.UNAVAILABLE;
      this.providerDetail = BehaviorProviderPresentation.readyDetail(this.temporalDegraded);
      return;
    }
    try {
      const loaded: mindSporeLite.Model = await this.loadModel(MindSporeBehaviorProvider.V34_MODEL_PATH);
      if (!this.runToken.isCurrent(run)) return;
      const inputs: mindSporeLite.MSTensor[] = loaded.getInputs();
      if (!this.hasInputContract(inputs, 4, BehaviorFullFramePreprocessor.FRAME_SIZE)) {
        throw new Error('V3.4 input contract mismatch');
      }
      const temporalLoaded: mindSporeLite.Model | null = await this.loadTemporalModel();
      if (!this.runToken.isCurrent(run)) return;
      const v32Loaded: mindSporeLite.Model | null = await this.loadV32Model();
      if (!this.runToken.isCurrent(run)) return;
      this.model = loaded;
      this.temporalModel = temporalLoaded;
      this.v32Model = v32Loaded;
      this.temporalDegraded = temporalLoaded === null;
      this.providerStatus = FocusAssistStatus.UNAVAILABLE;
      this.providerDetail = BehaviorProviderPresentation.readyDetail(this.temporalDegraded);
    } catch (error) {
      if (!this.runToken.isCurrent(run)) return;
      this.model = null;
      this.temporalModel = null;
      this.v32Model = null;
      this.providerStatus = FocusAssistStatus.ERROR;
      this.providerDetail = 'V3.4 本地模型不可用，已停止行为提醒';
    }
  }

  async stop(): Promise<void> {
    if (this.sessionSummaryInitialized) this.sessionSummaryTracker.suspend(Date.now());
    this.runToken.invalidate();
    this.activeRun = 0;
    this.clearProductState();
    this.temporalSmoother.reset();
    this.signalProcessor.reset();
    this.continuityStateMachine.reset();
    this.presenceStateMachine.reset();
    this.currentDisplayState = BehaviorDisplayStates.observing();
    this.currentContinuityState = LearningContinuityState.OBSERVING;
    this.currentPresenceState = PresenceState.OBSERVING;
    this.providerStatus = FocusAssistStatus.UNAVAILABLE;
    this.providerDetail = this.model === null ? 'V3.4 本地模型尚未加载' :
      BehaviorProviderPresentation.readyDetail(this.temporalDegraded);
  }

  async analyze(frame: RgbaBehaviorFrame): Promise<FocusAssistSignal | undefined> {
    const run: number = this.activeRun;
    if (!this.runToken.isCurrent(run)) return undefined;
    const model: mindSporeLite.Model | null = this.model;
    const v32Model: mindSporeLite.Model | null = this.v32Model;
    const hasPersonRoi: boolean = frame.personBox.right - frame.personBox.left >= 2 &&
      frame.personBox.bottom - frame.personBox.top >= 2;
    const selected: BehaviorRuntimeModel = BehaviorModelSelection.select(
      model !== null, v32Model !== null, hasPersonRoi
    );
    if (selected === BehaviorRuntimeModel.UNAVAILABLE) {
      this.resetTemporalState();
      this.signal = undefined;
      this.reminderTracker.reset();
      this.providerStatus = FocusAssistStatus.UNAVAILABLE;
      this.providerDetail = '缺少可用模型，无法进行本地行为识别';
      return undefined;
    }
    try {
      this.providerStatus = FocusAssistStatus.RUNNING;
      let fused: BehaviorV34Result;
      let hasTemporalEvidence: boolean = false;
      if (selected === BehaviorRuntimeModel.V34 && model !== null) {
        const inputData: Float32Array | undefined = BehaviorRoiPreprocessor.toNchw(frame);
        if (inputData === undefined) throw new Error('V3.4 ROI preprocessing failed');
        const fullFrame: Float32Array | undefined = BehaviorFullFramePreprocessor.toChw(frame);
        if (fullFrame === undefined) throw new Error('full frame preprocessing failed');
        this.temporalFrames.push(fullFrame);
        const inputs: mindSporeLite.MSTensor[] = model.getInputs();
        inputs[0].setData(inputData.buffer);
        const outputs: mindSporeLite.MSTensor[] = await model.predict(inputs);
        if (!this.runToken.isCurrent(run)) return undefined;
        const result: BehaviorV34Result | undefined = this.decodeV34(outputs);
        if (result === undefined) throw new Error('V3.4 output contract mismatch');
        const rankedSingle: BehaviorV34Label = this.topSingleLabel(result);
        const shouldRunTemporal: boolean = this.temporalModel !== null &&
          BehaviorHybridPolicy.shouldRunTemporal(
            result, this.previousSingleTop, frame.timestamp, this.lastTemporalAtMs,
            this.temporalFrames.size()
          );
        this.previousSingleTop = rankedSingle;
        if (shouldRunTemporal) {
          await this.runTemporal(frame.timestamp, run);
          if (!this.runToken.isCurrent(run)) return undefined;
        }
        fused = this.fuse(result);
        hasTemporalEvidence = this.cachedTemporal !== undefined;
      } else {
        const v32Result: BehaviorV34Result | undefined = await this.runV32(v32Model, frame);
        if (!this.runToken.isCurrent(run)) return undefined;
        if (v32Result === undefined) throw new Error('V3.2 output contract mismatch');
        fused = v32Result;
        this.previousSingleTop = this.topSingleLabel(fused);
      }
      const smoothedProbabilities: number[] = this.temporalSmoother.smooth(fused.probabilities);
      const smoothedFused: BehaviorV34Result = {
        label: fused.label,
        confidence: fused.confidence,
        margin: fused.margin,
        isStable: fused.isStable,
        probabilities: smoothedProbabilities
      };
      const displayState: BehaviorDisplayState = this.signalProcessor.processDisplayState(
        smoothedFused, frame.timestamp
      );
      const continuityResult = this.continuityStateMachine.process(displayState, frame.timestamp);
      const behaviorEvidence: boolean = smoothedFused.isStable &&
        this.isStudyBehavior(smoothedFused.label);
      const presenceSnapshot = this.presenceStateMachine.process(
        frame.timestamp, hasPersonRoi, false, behaviorEvidence
      );
      this.signalProcessor.process(smoothedFused, frame.timestamp);
      this.currentDisplayState = displayState;
      this.currentContinuityState = continuityResult.state;
      this.currentPresenceState = presenceSnapshot.state;
      const next: FocusAssistSignal = {
        label: smoothedFused.label,
        confidence: smoothedFused.confidence,
        isStable: smoothedFused.isStable,
        timestamp: frame.timestamp,
        modelVersion: BehaviorProviderPresentation.modelVersion(hasTemporalEvidence),
        displayStateKind: displayState.kind,
        continuityState: continuityResult.state,
        presenceState: presenceSnapshot.state
      };
      this.signal = next;
      const reminder: string = this.reminderTracker.process(smoothedFused, frame.timestamp);
      this.sessionSummaryTracker.process(smoothedFused, frame.timestamp, reminder);
      this.providerStatus = FocusAssistStatus.RUNNING;
      this.providerDetail = BehaviorProviderPresentation.detail(
        this.temporalDegraded, smoothedFused.label, hasTemporalEvidence
      );
      return next;
    } catch (error) {
      if (!this.runToken.isCurrent(run)) return undefined;
      this.resetTemporalState();
      this.signal = undefined;
      this.reminderTracker.reset();
      this.providerStatus = FocusAssistStatus.ERROR;
      this.providerDetail = '本帧推理失败，未触发行为提醒';
      return undefined;
    }
  }

  private async loadModel(path: string): Promise<mindSporeLite.Model> {
    const bytes: Uint8Array = await this.manager.getRawFileContent(path);
    const modelBuffer: ArrayBuffer = new ArrayBuffer(bytes.byteLength);
    new Uint8Array(modelBuffer).set(bytes);
    return await mindSporeLite.loadModelFromBuffer(modelBuffer);
  }

  private async loadTemporalModel(): Promise<mindSporeLite.Model | null> {
    try {
      const loaded: mindSporeLite.Model = await this.loadModel(MindSporeBehaviorProvider.TSM_MODEL_PATH);
      const inputs: mindSporeLite.MSTensor[] = loaded.getInputs();
      if (!this.hasInputContract(inputs, 5, BehaviorTsmContract.INPUT_FRAME_COUNT *
        BehaviorFullFramePreprocessor.FRAME_SIZE)) {
        throw new Error('TSM input contract mismatch');
      }
      return loaded;
    } catch (error) {
      return null;
    }
  }

  private async loadV32Model(): Promise<mindSporeLite.Model | null> {
    try {
      const loaded: mindSporeLite.Model = await this.loadModel(MindSporeBehaviorProvider.V32_MODEL_PATH);
      const inputs: mindSporeLite.MSTensor[] = loaded.getInputs();
      if (!this.hasInputContract(inputs, 4, BehaviorFullFramePreprocessor.FRAME_SIZE)) {
        throw new Error('V3.2 input contract mismatch');
      }
      return loaded;
    } catch (error) {
      return null;
    }
  }

  private hasInputContract(inputs: mindSporeLite.MSTensor[], rank: number, elementNum: number): boolean {
    return inputs.length === 1 && inputs[0].shape.length === rank && inputs[0].elementNum === elementNum;
  }

  private decodeV34(outputs: mindSporeLite.MSTensor[]): BehaviorV34Result | undefined {
    if (outputs.length !== 1 || outputs[0].elementNum !== 4) return undefined;
    const raw: Float32Array = new Float32Array(outputs[0].getData());
    if (raw.length !== 4) return undefined;
    return BehaviorV34OutputContract.decode([raw[0], raw[1], raw[2], raw[3]]);
  }

  private decodeV32(outputs: mindSporeLite.MSTensor[]): BehaviorV34Result | undefined {
    if (outputs.length !== 1 || outputs[0].elementNum !== 2) return undefined;
    const raw: Float32Array = new Float32Array(outputs[0].getData());
    if (raw.length !== 2) return undefined;
    if (!Number.isFinite(raw[0]) || !Number.isFinite(raw[1])) return undefined;
    const maxLogit: number = Math.max(raw[0], raw[1]);
    const exp0: number = Math.exp(raw[0] - maxLogit);
    const exp1: number = Math.exp(raw[1] - maxLogit);
    const sum: number = exp0 + exp1;
    if (!Number.isFinite(sum) || sum <= 0) return undefined;
    const probIdle: number = exp0 / sum;
    const probVisibleStudy: number = exp1 / sum;
    const probabilities: number[] = [probVisibleStudy, 0, 0, probIdle];
    const best: number = Math.max(probVisibleStudy, probIdle);
    const margin: number = Math.abs(probVisibleStudy - probIdle);
    const accepted: boolean = best >= BehaviorV34Decision.MIN_CONFIDENCE &&
      margin >= BehaviorV34Decision.MIN_MARGIN;
    const label: BehaviorV34Label = probVisibleStudy >= probIdle ?
      BehaviorV34Label.READ : BehaviorV34Label.NO_VISIBLE_STUDY;
    return {
      label: accepted ? label : BehaviorV34Label.CONTINUE_OBSERVING,
      confidence: best,
      margin: margin,
      isStable: accepted,
      probabilities: probabilities
    };
  }

  private preprocessFullFrameNchw(frame: RgbaBehaviorFrame): Float32Array | undefined {
    const fullBox: PersonBox = {
      left: 0, top: 0, right: frame.width, bottom: frame.height
    };
    const fullFrame: RgbaBehaviorFrame = {
      pixels: frame.pixels,
      width: frame.width,
      height: frame.height,
      personBox: fullBox,
      timestamp: frame.timestamp
    };
    return BehaviorRoiPreprocessor.toNchw(fullFrame);
  }

  private async runV32(v32Model: mindSporeLite.Model | null,
    frame: RgbaBehaviorFrame): Promise<BehaviorV34Result | undefined> {
    if (v32Model === null) return undefined;
    const inputData: Float32Array | undefined = this.preprocessFullFrameNchw(frame);
    if (inputData === undefined) return undefined;
    const inputs: mindSporeLite.MSTensor[] = v32Model.getInputs();
    inputs[0].setData(inputData.buffer);
    const outputs: mindSporeLite.MSTensor[] = await v32Model.predict(inputs);
    return this.decodeV32(outputs);
  }

  private isStudyBehavior(label: BehaviorV34Label): boolean {
    return label === BehaviorV34Label.READ || label === BehaviorV34Label.WRITE ||
      label === BehaviorV34Label.COMPUTER;
  }

  private topSingleLabel(result: BehaviorV34Result): BehaviorV34Label {
    if (result.probabilities.length !== 4) return BehaviorV34Label.CONTINUE_OBSERVING;
    let bestIndex: number = 0;
    for (let index: number = 1; index < result.probabilities.length; index++) {
      if (result.probabilities[index] > result.probabilities[bestIndex]) bestIndex = index;
    }
    const labels: BehaviorV34Label[] = [
      BehaviorV34Label.READ,
      BehaviorV34Label.WRITE,
      BehaviorV34Label.PHONE_INTERACTION,
      BehaviorV34Label.NO_VISIBLE_STUDY
    ];
    return labels[bestIndex];
  }

  private async runTemporal(timestamp: number, run: number): Promise<void> {
    const model: mindSporeLite.Model | null = this.temporalModel;
    const inputData: Float32Array | undefined = this.temporalFrames.toModelInput();
    if (model === null || inputData === undefined) return;
    this.lastTemporalAtMs = timestamp;
    try {
      const inputs: mindSporeLite.MSTensor[] = model.getInputs();
      if (!this.hasInputContract(inputs, 5, inputData.length)) throw new Error('TSM input contract mismatch');
      inputs[0].setData(inputData.buffer);
      const outputs: mindSporeLite.MSTensor[] = await model.predict(inputs);
      if (!this.runToken.isCurrent(run)) return;
      if (outputs.length !== 1 || outputs[0].elementNum !== 5) throw new Error('TSM output contract mismatch');
      const raw: Float32Array = new Float32Array(outputs[0].getData());
      if (raw.length !== 5) throw new Error('TSM output data mismatch');
      const result: BehaviorTsmResult = BehaviorTsmContract.decode([raw[0], raw[1], raw[2], raw[3], raw[4]]);
      if (!result.isStable) throw new Error('TSM logits rejected');
      this.cachedTemporal = result;
      if (result.label === BehaviorV34Label.COMPUTER) {
        this.computerConfirmationCount = Math.min(2, this.computerConfirmationCount + 1);
      } else {
        this.computerConfirmationCount = 0;
      }
    } catch (error) {
      if (!this.runToken.isCurrent(run)) return;
      this.temporalModel = null;
      this.temporalDegraded = true;
      this.cachedTemporal = undefined;
      this.computerConfirmationCount = 0;
      this.providerDetail = 'TSM V4 推理失败，已降级为 V3.4 行为识别';
    }
  }

  private fuse(single: BehaviorV34Result): BehaviorV34Result {
    const temporal: BehaviorTsmResult | undefined = this.cachedTemporal;
    if (temporal === undefined) return single;
    const decision = BehaviorHybridPolicy.fuse(
      single, temporal, this.computerConfirmationCount >= 2
    );
    return {
      label: decision.label,
      confidence: decision.confidence,
      margin: decision.margin,
      isStable: decision.isStable,
      probabilities: decision.probabilities
    };
  }

  private resetTemporalState(): void {
    this.temporalFrames.reset();
    this.previousSingleTop = undefined;
    this.lastTemporalAtMs = 0;
    this.cachedTemporal = undefined;
    this.computerConfirmationCount = 0;
  }

  private clearProductState(): void {
    this.signal = undefined;
    this.resetTemporalState();
    this.reminderTracker.reset();
  }
}
