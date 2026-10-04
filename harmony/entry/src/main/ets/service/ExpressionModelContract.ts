/** Tensor contract for the deployed Harmony local expression/state model. */
export class ExpressionModelContract {
  static readonly NHWC_INPUT_SHAPE: number[] = [1, 96, 96, 3];
  static readonly NCHW_INPUT_SHAPE: number[] = [1, 3, 96, 96];
  static readonly OUTPUT_SHAPE: number[] = [1, 10];
  static readonly INPUT_ELEMENT_COUNT: number = 96 * 96 * 3;
  static readonly OUTPUT_ELEMENT_COUNT: number = 10;
  static readonly FLOAT32_BYTES: number = 4;

  static acceptsInput(shape: number[], elementCount: number, layout: string = 'NCHW'): boolean {
    const expectedShape: number[] = layout === 'NCHW' ? ExpressionModelContract.NCHW_INPUT_SHAPE :
      layout === 'NHWC' ? ExpressionModelContract.NHWC_INPUT_SHAPE : [];
    return expectedShape.length > 0 && ExpressionModelContract.matches(shape, expectedShape) &&
      elementCount === ExpressionModelContract.INPUT_ELEMENT_COUNT;
  }

  static acceptsOutput(shape: number[], elementCount: number, byteLength: number,
    expectedCount: number = ExpressionModelContract.OUTPUT_ELEMENT_COUNT): boolean {
    const expectedShape: number[] = [1, expectedCount];
    return ExpressionModelContract.matches(shape, expectedShape) &&
      elementCount === expectedCount &&
      byteLength === expectedCount * ExpressionModelContract.FLOAT32_BYTES;
  }

  private static matches(actual: number[], expected: number[]): boolean {
    if (actual.length !== expected.length) return false;
    for (let index: number = 0; index < expected.length; index++) {
      if (actual[index] !== expected[index]) return false;
    }
    return true;
  }
}
