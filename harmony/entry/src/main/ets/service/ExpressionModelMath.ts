export interface ExpressionPrediction {
  label: string;
  confidence: number;
  probabilities: number[];
  stateLogits?: number[];
}

export interface ExpressionConfidenceCalibration {
  expression_temperature: number;
  state_scales: number[];
  state_biases: number[];
}

export interface ExpressionStateConfidences {
  boredom: number;
  confusion: number;
  frustration: number;
}

/** Pure preprocessing and output decoding used by the Harmony local model provider. */
export class ExpressionModelMath {
  private static readonly LABELS: string[] = [
    'angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise'
  ];
  private static readonly MEAN: number[] = [0.485, 0.456, 0.406];
  private static readonly STD: number[] = [0.229, 0.224, 0.225];

  static rgbaToGrayscaleNhwc(pixels: Uint8Array, width: number, height: number): Float32Array | undefined {
    if (width <= 0 || height <= 0 || pixels.length < width * height * 4) return undefined;
    const output: Float32Array = new Float32Array(width * height * 3);
    for (let index: number = 0; index < width * height; index++) {
      const source: number = index * 4;
      const gray: number = (0.299 * pixels[source] + 0.587 * pixels[source + 1] +
        0.114 * pixels[source + 2]) / 255.0;
      const target: number = index * 3;
      output[target] = (gray - ExpressionModelMath.MEAN[0]) / ExpressionModelMath.STD[0];
      output[target + 1] = (gray - ExpressionModelMath.MEAN[1]) / ExpressionModelMath.STD[1];
      output[target + 2] = (gray - ExpressionModelMath.MEAN[2]) / ExpressionModelMath.STD[2];
    }
    return output;
  }

  static rgbaToGrayscaleNchw(pixels: Uint8Array, width: number, height: number): Float32Array | undefined {
    if (width <= 0 || height <= 0 || pixels.length < width * height * 4) return undefined;
    const planeSize: number = width * height;
    const output: Float32Array = new Float32Array(planeSize * 3);
    for (let index: number = 0; index < planeSize; index++) {
      const source: number = index * 4;
      const gray: number = (0.299 * pixels[source] + 0.587 * pixels[source + 1] +
        0.114 * pixels[source + 2]) / 255.0;
      output[index] = (gray - ExpressionModelMath.MEAN[0]) / ExpressionModelMath.STD[0];
      output[planeSize + index] = (gray - ExpressionModelMath.MEAN[1]) / ExpressionModelMath.STD[1];
      output[planeSize * 2 + index] = (gray - ExpressionModelMath.MEAN[2]) / ExpressionModelMath.STD[2];
    }
    return output;
  }

  static decode(logits: Float32Array, temperature: number = 1.0): ExpressionPrediction | undefined {
    if (logits.length !== ExpressionModelMath.LABELS.length ||
      !Number.isFinite(temperature) || temperature <= 0) return undefined;
    if (!Number.isFinite(logits[0])) return undefined;
    let maximum: number = logits[0] / temperature;
    for (let index: number = 1; index < logits.length; index++) {
      if (!Number.isFinite(logits[index])) return undefined;
      maximum = Math.max(maximum, logits[index] / temperature);
    }
    const exponentials: number[] = [];
    let sum: number = 0;
    for (let index: number = 0; index < logits.length; index++) {
      if (!Number.isFinite(logits[index])) return undefined;
      const value: number = Math.exp(logits[index] / temperature - maximum);
      exponentials.push(value);
      sum += value;
    }
    if (!Number.isFinite(sum) || sum <= 0) return undefined;
    let bestIndex: number = 0;
    for (let index: number = 1; index < exponentials.length; index++) {
      if (exponentials[index] > exponentials[bestIndex]) bestIndex = index;
    }
    const probabilities: number[] = exponentials.map((value: number) => value / sum);
    return { label: ExpressionModelMath.LABELS[bestIndex], confidence: probabilities[bestIndex], probabilities };
  }

  static calibrateStates(logits: number[], calibration: ExpressionConfidenceCalibration):
    ExpressionStateConfidences | undefined {
    if (logits.length !== 3 || calibration.state_scales.length !== 3 || calibration.state_biases.length !== 3) {
      return undefined;
    }
    const probabilities: number[] = [];
    for (let index: number = 0; index < 3; index++) {
      const logit: number = logits[index];
      const scale: number = calibration.state_scales[index];
      const bias: number = calibration.state_biases[index];
      if (!Number.isFinite(logit) || !Number.isFinite(scale) || scale < 0 || !Number.isFinite(bias)) {
        return undefined;
      }
      const calibrated: number = logit * scale + bias;
      const probability: number = calibrated >= 0 ?
        1 / (1 + Math.exp(-calibrated)) : Math.exp(calibrated) / (1 + Math.exp(calibrated));
      probabilities.push(probability);
    }
    return { boredom: probabilities[0], confusion: probabilities[1], frustration: probabilities[2] };
  }
}
