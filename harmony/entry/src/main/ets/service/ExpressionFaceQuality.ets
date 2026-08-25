export interface ExpressionFaceQualityMetrics {
  faceCount: number;
  faceRatio: number;
  sharpness: number;
  brightness: number;
}

export interface ExpressionFaceQualityDecision {
  accepted: boolean;
  reason: string;
}

export interface ExpressionPixelQuality {
  sharpness: number;
  brightness: number;
}

/** Conservative, platform-neutral abstention gate applied before inference. */
export class ExpressionFaceQuality {
  static evaluate(metrics: ExpressionFaceQualityMetrics): ExpressionFaceQualityDecision {
    if (metrics.faceCount !== 1) return { accepted: false, reason: 'MULTIPLE_FACES' };
    if (metrics.faceRatio < 0.12) return { accepted: false, reason: 'TOO_SMALL' };
    if (metrics.sharpness < 18) return { accepted: false, reason: 'BLUR' };
    if (metrics.brightness < 40 || metrics.brightness > 225) {
      return { accepted: false, reason: 'LOW_LIGHT' };
    }
    return { accepted: true, reason: 'ACCEPTED' };
  }

  static measureRgba(pixels: Uint8Array, width: number, height: number): ExpressionPixelQuality {
    if (width <= 0 || height <= 0 || pixels.length < width * height * 4) {
      return { sharpness: 0, brightness: 0 };
    }
    const stride: number = Math.max(1, Math.floor(Math.max(width, height) / 64));
    let brightnessTotal: number = 0;
    let brightnessSamples: number = 0;
    let edgeEnergy: number = 0;
    let edgeSamples: number = 0;
    for (let y: number = 0; y < height; y += stride) {
      for (let x: number = 0; x < width; x += stride) {
        const current: number = ExpressionFaceQuality.luminance(pixels, (y * width + x) * 4);
        brightnessTotal += current;
        brightnessSamples++;
        if (x + stride < width) {
          const right: number = ExpressionFaceQuality.luminance(pixels, (y * width + x + stride) * 4);
          edgeEnergy += (current - right) * (current - right);
          edgeSamples++;
        }
        if (y + stride < height) {
          const down: number = ExpressionFaceQuality.luminance(pixels, ((y + stride) * width + x) * 4);
          edgeEnergy += (current - down) * (current - down);
          edgeSamples++;
        }
      }
    }
    return {
      sharpness: edgeSamples === 0 ? 0 : edgeEnergy / edgeSamples,
      brightness: brightnessSamples === 0 ? 0 : brightnessTotal / brightnessSamples
    };
  }

  private static luminance(pixels: Uint8Array, offset: number): number {
    return 0.299 * pixels[offset] + 0.587 * pixels[offset + 1] + 0.114 * pixels[offset + 2];
  }
}
