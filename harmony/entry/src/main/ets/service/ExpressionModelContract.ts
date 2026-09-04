/** Tensor contract for the deployed Harmony local expression model. */
export class ExpressionModelContract {
  static readonly INPUT_SHAPE: number[] = [1, 96, 96, 3];
  static readonly OUTPUT_SHAPE: number[] = [1, 7];
  static readonly INPUT_ELEMENT_COUNT: number = 96 * 96 * 3;
  static readonly OUTPUT_ELEMENT_COUNT: number = 7;
  static readonly FLOAT32_BYTES: number = 4;

  static acceptsInput(shape: number[], elementCount: number): boolean {
    return ExpressionModelContract.matches(shape, ExpressionModelContract.INPUT_SHAPE) &&
      elementCount === ExpressionModelContract.INPUT_ELEMENT_COUNT;
  }

  static acceptsOutput(shape: number[], elementCount: number, byteLength: number): boolean {
    return ExpressionModelContract.matches(shape, ExpressionModelContract.OUTPUT_SHAPE) &&
      elementCount === ExpressionModelContract.OUTPUT_ELEMENT_COUNT &&
      byteLength === ExpressionModelContract.OUTPUT_ELEMENT_COUNT * ExpressionModelContract.FLOAT32_BYTES;
  }

  private static matches(actual: number[], expected: number[]): boolean {
    if (actual.length !== expected.length) return false;
    for (let index: number = 0; index < expected.length; index++) {
      if (actual[index] !== expected[index]) return false;
    }
    return true;
  }
}
