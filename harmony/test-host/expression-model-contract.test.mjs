import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { ExpressionModelContract } from '../entry/src/main/ets/service/ExpressionModelContract.ts';

test('packaged multitask model matches its NCHW metadata and calibrated ten-label contract', () => {
  const assetRoot = new URL('../entry/src/main/resources/rawfile/models/expression/', import.meta.url);
  const metadata = JSON.parse(readFileSync(new URL('preprocessing.json', assetRoot), 'utf8'));
  const model = readFileSync(new URL('campusmate_expression_v2.ms', assetRoot));
  assert.equal(metadata.input_layout, 'NCHW');
  assert.equal(metadata.input_dtype, 'float32');
  assert.equal(ExpressionModelContract.acceptsInput(metadata.input_shape, 96 * 96 * 3, metadata.input_layout), true);
  assert.equal(metadata.output_size, 10);
  assert.equal(metadata.output_type, 'logits');
  assert.deepEqual(metadata.output_order, ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise',
    'boredom', 'confusion', 'frustration']);
  assert.equal(metadata.state_window_frames, 4);
  assert.equal(metadata.state_window_max_age_ms, 5000);
  assert.equal(metadata.states_are_independent, true);
  assert.equal(metadata.confidence_calibration.fitted_on, 'validation');
  assert.equal(metadata.confidence_calibration.positive_definition, 'DAiSEE level >= 2');
  assert.ok(Number.isFinite(metadata.confidence_calibration.expression_temperature)
    && metadata.confidence_calibration.expression_temperature > 0);
  assert.equal(metadata.confidence_calibration.state_scales.length, 3);
  assert.equal(metadata.confidence_calibration.state_biases.length, 3);
  assert.ok(metadata.confidence_calibration.state_scales.every(value => Number.isFinite(value) && value >= 0));
  assert.ok(metadata.confidence_calibration.state_biases.every(Number.isFinite));
  assert.equal(model.length, metadata.model_size_bytes);
  assert.equal(createHash('sha256').update(model).digest('hex'), metadata.model_sha256);
});
import { ExpressionModelMath } from '../entry/src/main/ets/service/ExpressionModelMath.ts';

test('requires NCHW for multitask and accepts NHWC only when legacy layout is explicit', () => {
  assert.equal(ExpressionModelContract.acceptsInput([1, 3, 96, 96], 96 * 96 * 3), true);
  assert.equal(ExpressionModelContract.acceptsInput([1, 96, 96, 3], 96 * 96 * 3), false);
  assert.equal(ExpressionModelContract.acceptsInput([1, 96, 96, 3], 96 * 96 * 3, 'NHWC'), true);
  assert.equal(ExpressionModelContract.acceptsInput([1, 3, 96, 96], 96 * 96 * 3, 'NHWC'), false);
  assert.equal(ExpressionModelContract.acceptsInput([1, 3, 96, 96], 96 * 96 * 3, 'unsupported'), false);
  assert.equal(ExpressionModelContract.acceptsInput([1, 3, 96, 96], 96 * 96), false);
});

test('requires the deployed float32 ten-logit output tensor and supports explicit legacy metadata', () => {
  assert.equal(ExpressionModelContract.acceptsOutput([1, 10], 10, 40), true);
  assert.equal(ExpressionModelContract.acceptsOutput([10], 10, 40), false);
  assert.equal(ExpressionModelContract.acceptsOutput([1, 10], 10, 20), false);
  assert.equal(ExpressionModelContract.acceptsOutput([1, 7], 7, 28, 7), true);
  assert.equal(ExpressionModelContract.acceptsOutput([1, 7], 7, 28), false);
});

test('converts interleaved RGBA grayscale pixels into normalized NCHW RGB planes', () => {
  const pixels = new Uint8Array([255, 0, 0, 255, 0, 255, 0, 255]);
  const nhwc = ExpressionModelMath.rgbaToGrayscaleNhwc(pixels, 2, 1);
  const nchw = ExpressionModelMath.rgbaToGrayscaleNchw(pixels, 2, 1);
  assert.deepEqual(Array.from(nchw), [nhwc[0], nhwc[3], nhwc[1], nhwc[4], nhwc[2], nhwc[5]]);
});
