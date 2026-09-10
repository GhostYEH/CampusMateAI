import { resourceManager } from '@kit.LocalizationKit';
import { util } from '@kit.ArkTS';
import { ExpressionThresholds, DEFAULT_EXPRESSION_THRESHOLDS } from './ExpressionSignalProcessor';

export interface ExpressionPreprocessingConfig {
  input_size: number;
  input_channels: number;
  input_color_mode: string;
  mean: number[];
  std: number[];
  confidence_threshold: number;
  class_thresholds: ExpressionThresholds;
  stable_frame_count: number;
  ema_alpha: number;
  max_age_ms: number;
  model_version: string;
}

const CONFIG_PATH: string = 'models/expression/preprocessing.json';

export class ExpressionPreprocessingLoader {
  static async load(manager: resourceManager.ResourceManager): Promise<ExpressionPreprocessingConfig> {
    const bytes: Uint8Array = await manager.getRawFileContent(CONFIG_PATH);
    const text: string = new util.TextDecoder().decode(bytes);
    const raw: Record<string, Object> = JSON.parse(text) as Record<string, Object>;
    const classThresholdsRaw: Record<string, number> = raw['class_thresholds'] as Record<string, number>;
    return {
      input_size: (raw['input_size'] as number) ?? 96,
      input_channels: (raw['input_channels'] as number) ?? 3,
      input_color_mode: (raw['input_color_mode'] as string) ?? 'grayscale_replicated',
      mean: (raw['mean'] as number[]) ?? [0.485, 0.456, 0.406],
      std: (raw['std'] as number[]) ?? [0.229, 0.224, 0.225],
      confidence_threshold: (raw['confidence_threshold'] as number) ?? 0.7,
      class_thresholds: classThresholdsRaw ?? DEFAULT_EXPRESSION_THRESHOLDS,
      stable_frame_count: (raw['stable_frame_count'] as number) ?? 3,
      ema_alpha: (raw['ema_alpha'] as number) ?? 0.4,
      max_age_ms: (raw['max_age_ms'] as number) ?? 5000,
      model_version: (raw['model_version'] as string) ?? 'expression-resnet18-multiv2-v1-mslite'
    };
  }
}
