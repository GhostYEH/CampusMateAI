import assert from 'node:assert/strict';
import test from 'node:test';
import { ExpressionModelContract } from '../entry/src/main/ets/service/ExpressionModelContract.ts';

test('accepts only the deployed NHWC expression input tensor', () => {
  assert.equal(ExpressionModelContract.acceptsInput([1, 96, 96, 3], 96 * 96 * 3), true);
  assert.equal(ExpressionModelContract.acceptsInput([1, 3, 96, 96], 96 * 96 * 3), false);
  assert.equal(ExpressionModelContract.acceptsInput([1, 96, 96, 3], 96 * 96), false);
});

test('requires the deployed float32 seven-logit output tensor', () => {
  assert.equal(ExpressionModelContract.acceptsOutput([1, 7], 7, 28), true);
  assert.equal(ExpressionModelContract.acceptsOutput([7], 7, 28), false);
  assert.equal(ExpressionModelContract.acceptsOutput([1, 7], 7, 14), false);
});
