export interface ExpressionPrediction {
  label: string;
  confidence: number;
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

  static decode(logits: Float32Array): ExpressionPrediction | undefined {
    if (logits.length !== ExpressionModelMath.LABELS.length) return undefined;
    let maximum: number = logits[0];
    for (let index: number = 1; index < logits.length; index++) maximum = Math.max(maximum, logits[index]);
    const exponentials: number[] = [];
    let sum: number = 0;
    for (let index: number = 0; index < logits.length; index++) {
      const value: number = Math.exp(logits[index] - maximum);
      exponentials.push(value);
      sum += value;
    }
    if (!Number.isFinite(sum) || sum <= 0) return undefined;
    let bestIndex: number = 0;
    for (let index: number = 1; index < exponentials.length; index++) {
      if (exponentials[index] > exponentials[bestIndex]) bestIndex = index;
    }
    return { label: ExpressionModelMath.LABELS[bestIndex], confidence: exponentials[bestIndex] / sum };
  }
}
