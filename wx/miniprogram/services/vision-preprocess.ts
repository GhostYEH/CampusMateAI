export const EXPRESSION_INPUT_SIZE = 96
export const EXPRESSION_INPUT_SHAPE = [1, EXPRESSION_INPUT_SIZE, EXPRESSION_INPUT_SIZE, 3]

const CHANNEL_MEANS = [0.485, 0.456, 0.406]
const CHANNEL_STANDARD_DEVIATIONS = [0.229, 0.224, 0.225]

/** Matches the Android expression model metadata: grayscale-replicated RGB in NHWC order. */
export function preprocessExpressionFrame(
  buffer: ArrayBuffer,
  width: number,
  height: number,
  outputSize = EXPRESSION_INPUT_SIZE,
): Float32Array {
  if (width <= 0 || height <= 0 || outputSize <= 0) throw new Error('摄像头画面尺寸无效')
  const rgba = new Uint8Array(buffer)
  if (rgba.length < width * height * 4) throw new Error('摄像头画面数据不完整')

  const side = Math.min(width, height)
  const offsetX = Math.floor((width - side) / 2)
  const offsetY = Math.floor((height - side) / 2)
  const output = new Float32Array(outputSize * outputSize * 3)

  for (let y = 0; y < outputSize; y += 1) {
    const sourceY = offsetY + Math.min(side - 1, Math.floor(y * side / outputSize))
    for (let x = 0; x < outputSize; x += 1) {
      const sourceX = offsetX + Math.min(side - 1, Math.floor(x * side / outputSize))
      const sourceIndex = (sourceY * width + sourceX) * 4
      const gray = (0.299 * rgba[sourceIndex] + 0.587 * rgba[sourceIndex + 1] + 0.114 * rgba[sourceIndex + 2]) / 255
      const targetIndex = (y * outputSize + x) * 3
      for (let channel = 0; channel < 3; channel += 1) {
        output[targetIndex + channel] = (gray - CHANNEL_MEANS[channel]) / CHANNEL_STANDARD_DEVIATIONS[channel]
      }
    }
  }
  return output
}
