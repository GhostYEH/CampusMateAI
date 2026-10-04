import { resourceManager } from '@kit.LocalizationKit';
import { util } from '@kit.ArkTS';
import { ExpressionThresholds, DEFAULT_EXPRESSION_THRESHOLDS } from './ExpressionSignalProcessor';
import { ExpressionConfidenceCalibration } from './ExpressionModelMath';

export interface ExpressionPreprocessingConfig {
  input_size: number;
  input_channels: number;
  input_layout: string;
  input_dtype: string;
  input_color_mode: string;
  mean: number[];
  std: number[];
  confidence_threshold: number;
  class_thresholds: ExpressionThresholds;
  stable_frame_count: number;
  ema_alpha: number;
  max_age_ms: number;
  model_version: string;
  output_size: number;
  output_order: string[];
  output_type: string;
  confidence_calibration: ExpressionConfidenceCalibration;
  state_window_frames: number;
  state_window_max_age_ms: number;
}

const CONFIG_PATH: string = 'models/expression/preprocessing.json';
const LEGACY_OUTPUT_ORDER: string[] = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise'];
const MULTITASK_OUTPUT_ORDER: string[] = LEGACY_OUTPUT_ORDER.concat(['boredom', 'confusion', 'frustration']);

export class ExpressionPreprocessingLoader {
  static async load(manager: resourceManager.ResourceManager): Promise<ExpressionPreprocessingConfig> {
    const bytes: Uint8Array = await manager.getRawFileContent(CONFIG_PATH);
    const text: string = new util.TextDecoder().decode(bytes);
    const raw: Record<string, Object> = JSON.parse(text) as Record<string, Object>;
    const outputSize: number = (raw['output_size'] as number) ?? 7;
    const inputSize: number = (raw['input_size'] as number) ?? 96;
    const inputChannels: number = (raw['input_channels'] as number) ?? 3;
    const inputLayout: string = (raw['input_layout'] as string) ?? (outputSize === 7 ? 'NHWC' : '');
    const inputDtype: string = (raw['input_dtype'] as string) ?? 'float32';
    const outputOrder: string[] = (raw['output_order'] as string[]) ?? LEGACY_OUTPUT_ORDER;
    const outputType: string = (raw['output_type'] as string) ?? 'logits';
    const classThresholdsRaw: Record<string, number> = raw['class_thresholds'] as Record<string, number>;
    const mean: number[] = (raw['mean'] as number[]) ?? [0.485, 0.456, 0.406];
    const std: number[] = (raw['std'] as number[]) ?? [0.229, 0.224, 0.225];
    const calibration: ExpressionConfidenceCalibration | undefined =
      raw['confidence_calibration'] as ExpressionConfidenceCalibration | undefined;
    if (outputSize !== 7 && outputSize !== 10) throw new Error('unsupported expression output size');
    if (inputSize !== 96 || inputChannels !== 3 || inputDtype !== 'float32') {
      throw new Error('unsupported expression input tensor metadata');
    }
    if ((outputSize === 10 && inputLayout !== 'NCHW') || (outputSize === 7 && inputLayout !== 'NHWC')) {
      throw new Error('expression input layout does not match the declared model generation');
    }
    if (!this.validNumbers(mean, 3, false) || !this.validNumbers(std, 3, true)) {
      throw new Error('invalid expression normalization metadata');
    }
    if (outputSize === 7 && (outputType !== 'logits' || !this.matchesOrder(outputOrder, LEGACY_OUTPUT_ORDER))) {
      throw new Error('invalid legacy expression output metadata');
    }
    if (outputSize === 10 && (outputType !== 'logits' ||
      !this.matchesOrder(outputOrder, MULTITASK_OUTPUT_ORDER) || calibration === undefined || calibration === null ||
      !Number.isFinite(calibration.expression_temperature) || calibration.expression_temperature <= 0 ||
      !this.validNumbers(calibration.state_scales, 3, false) ||
      !this.validNumbers(calibration.state_biases, 3, false) || calibration.state_scales.some((value: number) => value < 0) ||
      raw['state_window_frames'] !== 4 || raw['state_window_max_age_ms'] !== 5000)) {
      throw new Error('incomplete or invalid multitask expression metadata');
    }
    return {
      input_size: inputSize,
      input_channels: inputChannels,
      input_layout: inputLayout,
      input_dtype: inputDtype,
      input_color_mode: (raw['input_color_mode'] as string) ?? 'grayscale_replicated',
      mean,
      std,
      confidence_threshold: (raw['confidence_threshold'] as number) ?? 0.7,
      class_thresholds: classThresholdsRaw ?? DEFAULT_EXPRESSION_THRESHOLDS,
      stable_frame_count: (raw['stable_frame_count'] as number) ?? 3,
      ema_alpha: (raw['ema_alpha'] as number) ?? 0.4,
      max_age_ms: (raw['max_age_ms'] as number) ?? 5000,
      model_version: (raw['model_version'] as string) ?? 'expression-resnet18-multiv2-v1-mslite',
      output_size: outputSize,
      output_order: outputOrder,
      output_type: outputType,
      confidence_calibration: calibration ?? {
        expression_temperature: 1.0,
        state_scales: [1.0, 1.0, 1.0],
        state_biases: [0.0, 0.0, 0.0]
      },
      state_window_frames: (raw['state_window_frames'] as number) ?? 4,
      state_window_max_age_ms: (raw['state_window_max_age_ms'] as number) ?? 5000
    };
  }

  private static matchesOrder(actual: string[], expected: string[]): boolean {
    if (actual === undefined || actual === null || actual.length !== expected.length) return false;
    for (let index: number = 0; index < expected.length; index++) {
      if (actual[index] !== expected[index]) return false;
    }
    return true;
  }

  private static validNumbers(values: number[], length: number, positive: boolean): boolean {
    if (values === undefined || values === null || values.length !== length) return false;
    for (let index: number = 0; index < values.length; index++) {
      if (!Number.isFinite(values[index]) || (positive && values[index] <= 0)) return false;
    }
    return true;
  }
}
