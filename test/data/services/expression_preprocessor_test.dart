import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:campus_companion/data/services/expression_model_config.dart';
import 'package:campus_companion/data/services/expression_preprocessor.dart';
import 'package:image/image.dart' as img;

void main() {
  group('ExpressionPreprocessor - 人脸裁剪', () {
    test('faceCropEnabled=true 且 faceBox=null 时返回 null (表示无人脸)', () {
      final config = ExpressionModelConfig.fer2013Default();
      final preprocessor = ExpressionPreprocessor(config);
      final image = img.Image(width: 100, height: 100);

      final result = preprocessor.process(image, null);

      expect(result, isNull);
    });

    test('faceCropEnabled=true 时按 faceBox + padding 裁剪', () {
      final config = ExpressionModelConfig.fer2013Default();
      final preprocessor = ExpressionPreprocessor(config);
      final image = img.Image(width: 100, height: 100);
      // 填充不同颜色,便于验证裁剪边界
      img.fill(image, color: img.ColorRgb8(0, 0, 0));
      img.fillRect(
        image,
        x1: 30,
        y1: 30,
        x2: 70,
        y2: 70,
        color: img.ColorRgb8(255, 255, 255),
      );

      const faceBox = FaceBox(left: 30, top: 30, right: 70, bottom: 70);
      final tensor = preprocessor.process(image, faceBox);

      expect(tensor, isNotNull);
      // 输出张量长度 = H * W * C = 48 * 48 * 1
      expect(tensor!.length, 48 * 48 * 1);
    });

    test('faceBox 超出图像边界时 clamp 到合法范围', () {
      final config = ExpressionModelConfig.fer2013Default();
      final preprocessor = ExpressionPreprocessor(config);
      final image = img.Image(width: 50, height: 50);

      // faceBox 超出图像边界
      const faceBox = FaceBox(left: -20, top: -20, right: 100, bottom: 100);
      final tensor = preprocessor.process(image, faceBox);

      // 不应崩溃,clamp 后仍能输出合法张量
      expect(tensor, isNotNull);
      expect(tensor!.length, 48 * 48);
    });
  });

  group('ExpressionPreprocessor - 尺寸调整', () {
    test('输入大于目标尺寸时被降采样到 48x48', () {
      final config = ExpressionModelConfig.fer2013Default();
      final preprocessor = ExpressionPreprocessor(config);
      final image = img.Image(width: 200, height: 200);

      const faceBox = FaceBox(left: 50, top: 50, right: 150, bottom: 150);
      final tensor = preprocessor.process(image, faceBox);

      expect(tensor, isNotNull);
      expect(tensor!.length, 48 * 48);
    });

    test('输入小于目标尺寸时被上采样到 48x48', () {
      final config = ExpressionModelConfig.fer2013Default();
      final preprocessor = ExpressionPreprocessor(config);
      final image = img.Image(width: 24, height: 24);

      const faceBox = FaceBox(left: 4, top: 4, right: 20, bottom: 20);
      final tensor = preprocessor.process(image, faceBox);

      expect(tensor, isNotNull);
      expect(tensor!.length, 48 * 48);
    });
  });

  group('ExpressionPreprocessor - 通道转换', () {
    test('channels=1 时输出灰度张量 (按 BT.601 加权)', () {
      final config = ExpressionModelConfig.fer2013Default();
      final preprocessor = ExpressionPreprocessor(config);
      // 纯红 100x100 图像
      final image = img.Image(width: 100, height: 100);
      img.fill(image, color: img.ColorRgb8(255, 0, 0));

      const faceBox = FaceBox(left: 10, top: 10, right: 90, bottom: 90);
      final tensor = preprocessor.process(image, faceBox);

      expect(tensor, isNotNull);
      // 红色按 BT.601: Y = 0.299*255 = 76.245 → /255.0 ≈ 0.299
      final gray = tensor![0];
      expect(gray, closeTo(0.299, 0.01));
    });

    test('channels=3 (RGB) 时输出 3 通道张量', () {
      const config = ExpressionModelConfig(
        labels: [
          'angry',
          'disgust',
          'fear',
          'happy',
          'neutral',
          'sad',
          'surprise',
        ],
        inputHeight: 48,
        inputWidth: 48,
        channels: 3,
        colorMode: 'rgb',
        normalization: ExpressionNormalization.divide255(),
        resizeMethod: 'bilinear',
        faceCropEnabled: false, // 不裁剪,直接处理整图
        faceCropPaddingRatio: 0.2,
        outputClasses: 7,
        outputFormat: 'softmax',
        modelVersion: 'test-rgb',
      );
      final preprocessor = ExpressionPreprocessor(config);
      // 红色像素
      final image = img.Image(width: 48, height: 48);
      img.fill(image, color: img.ColorRgb8(255, 0, 0));

      final tensor = preprocessor.process(image, null);

      expect(tensor, isNotNull);
      expect(tensor!.length, 48 * 48 * 3);
      // 第一个像素 R 通道应归一化为 1.0,G/B 为 0
      expect(tensor[0], closeTo(1.0, 1e-6)); // R
      expect(tensor[1], 0.0); // G
      expect(tensor[2], 0.0); // B
    });
  });

  group('ExpressionPreprocessor - 归一化', () {
    test('divide_255: 像素值被归一化到 [0, 1]', () {
      final config = ExpressionModelConfig.fer2013Default();
      final preprocessor = ExpressionPreprocessor(config);
      // 灰度 128 的图像
      final image = img.Image(width: 48, height: 48);
      img.fill(image, color: img.ColorRgb8(128, 128, 128));

      // faceCropEnabled=true,需提供 faceBox
      const faceBox = FaceBox(left: 4, top: 4, right: 44, bottom: 44);
      final tensor = preprocessor.process(image, faceBox);

      expect(tensor, isNotNull);
      // 128/255 ≈ 0.502
      expect(tensor![0], closeTo(128 / 255, 1e-3));
    });

    test('standardize: 像素值被归一化到均值附近', () {
      const config = ExpressionModelConfig(
        labels: [
          'angry',
          'disgust',
          'fear',
          'happy',
          'neutral',
          'sad',
          'surprise',
        ],
        inputHeight: 48,
        inputWidth: 48,
        channels: 1,
        colorMode: 'grayscale',
        normalization: ExpressionNormalization(
          method: 'standardize',
          mean: [0.5],
          std: [0.5],
        ),
        resizeMethod: 'bilinear',
        faceCropEnabled: false,
        faceCropPaddingRatio: 0.2,
        outputClasses: 7,
        outputFormat: 'softmax',
        modelVersion: 'test-std',
      );
      final preprocessor = ExpressionPreprocessor(config);
      final image = img.Image(width: 48, height: 48);
      img.fill(image, color: img.ColorRgb8(255, 255, 255)); // 白色

      final tensor = preprocessor.process(image, null);

      expect(tensor, isNotNull);
      // (255/255 - 0.5) / 0.5 = 1.0
      expect(tensor![0], closeTo(1.0, 1e-3));
    });
  });

  group('ExpressionPreprocessor - 张量形状', () {
    test('NHWC 格式: 长度 = H * W * C', () {
      final config = ExpressionModelConfig.fer2013Default();
      final preprocessor = ExpressionPreprocessor(config);
      final image = img.Image(width: 100, height: 100);

      const faceBox = FaceBox(left: 10, top: 10, right: 90, bottom: 90);
      final tensor = preprocessor.process(image, faceBox);

      expect(tensor, isNotNull);
      expect(tensor!.length, 48 * 48 * 1);
      // 类型为 Float32List
      expect(tensor, isA<Float32List>());
    });
  });
}
