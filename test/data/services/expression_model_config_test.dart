import 'package:flutter_test/flutter_test.dart';
import 'package:campus_companion/data/models/expression.dart';
import 'package:campus_companion/data/services/expression_model_config.dart';

void main() {
  // rootBundle.loadString 需要 TestWidgetsFlutterBinding 初始化才能在测试中加载 asset
  TestWidgetsFlutterBinding.ensureInitialized();

  group('ExpressionModelConfig - 从 JSON 解析', () {
    test('完整 preprocess.json + labels.json 解析为正确配置', () {
      final preprocess = {
        'input_shape': [1, 48, 48, 1],
        'input_size': [48, 48],
        'channels': 1,
        'color_mode': 'grayscale',
        'normalization': {'method': 'divide_255'},
        'resize_method': 'bilinear',
        'face_crop': {'enabled': true, 'padding_ratio': 0.2},
        'output_classes': 7,
        'output_format': 'softmax',
        'model_version': 'mobilenetv3-fer2013-v1.0',
      };
      final labels = {
        'labels': [
          'angry',
          'disgust',
          'fear',
          'happy',
          'neutral',
          'sad',
          'surprise',
        ],
        'version': 'fer2013-v1.0',
      };

      final config = ExpressionModelConfig.fromJson(
        preprocessJson: preprocess,
        labelsJson: labels,
      );

      expect(config.inputHeight, 48);
      expect(config.inputWidth, 48);
      expect(config.channels, 1);
      expect(config.colorMode, 'grayscale');
      expect(config.outputClasses, 7);
      expect(config.outputFormat, 'softmax');
      expect(config.modelVersion, 'mobilenetv3-fer2013-v1.0');
      expect(config.faceCropEnabled, isTrue);
      expect(config.faceCropPaddingRatio, 0.2);
      expect(config.labels.length, 7);
    });

    test(
        '标签顺序符合 FER2013 标准 (angry, disgust, fear, happy, neutral, sad, surprise)',
        () {
      final preprocess = {
        'input_size': [48, 48],
        'channels': 1,
        'output_classes': 7,
      };
      final labels = {
        'labels': [
          'angry',
          'disgust',
          'fear',
          'happy',
          'neutral',
          'sad',
          'surprise',
        ],
      };

      final config = ExpressionModelConfig.fromJson(
        preprocessJson: preprocess,
        labelsJson: labels,
      );

      // 标签顺序必须与模型输出维度一一对应
      expect(config.labels[0], 'angry');
      expect(config.labels[1], 'disgust');
      expect(config.labels[2], 'fear');
      expect(config.labels[3], 'happy');
      expect(config.labels[4], 'neutral');
      expect(config.labels[5], 'sad');
      expect(config.labels[6], 'surprise');
    });

    test('labels.json 缺失时使用 FER2013 标准顺序兜底', () {
      final preprocess = {
        'input_size': [48, 48],
        'channels': 1,
        'output_classes': 7,
      };

      final config = ExpressionModelConfig.fromJson(
        preprocessJson: preprocess,
        labelsJson: null,
      );

      expect(config.labels, [
        'angry',
        'disgust',
        'fear',
        'happy',
        'neutral',
        'sad',
        'surprise',
      ]);
    });

    test('input_shape 缺失时默认 [1, 48, 48, 1]', () {
      final preprocess = <String, dynamic>{
        'channels': 1,
        'output_classes': 7,
      };

      final config = ExpressionModelConfig.fromJson(
        preprocessJson: preprocess,
      );

      expect(config.tensorInputShape, [1, 48, 48, 1]);
    });
  });

  group('ExpressionModelConfig - 校验', () {
    test('标签数与 output_classes 不匹配时抛异常', () {
      final preprocess = {
        'input_size': [48, 48],
        'channels': 1,
        'output_classes': 7,
      };
      final labels = {
        'labels': ['angry', 'happy'], // 只有 2 个
      };

      final config = ExpressionModelConfig.fromJson(
        preprocessJson: preprocess,
        labelsJson: labels,
      );

      expect(
        config.validate,
        throwsA(isA<ModelConfigException>()),
      );
    });

    test('output_classes != 7 时抛异常 (本项目仅支持 FER2013 七类)', () {
      final preprocess = {
        'input_size': [48, 48],
        'channels': 1,
        'output_classes': 5,
      };

      final config = ExpressionModelConfig.fromJson(
        preprocessJson: preprocess,
      );

      expect(
        config.validate,
        throwsA(isA<ModelConfigException>()),
      );
    });

    test('channels 不是 1 或 3 时抛异常', () {
      final preprocess = {
        'input_size': [48, 48],
        'channels': 4,
        'output_classes': 7,
      };

      final config = ExpressionModelConfig.fromJson(
        preprocessJson: preprocess,
      );

      expect(
        config.validate,
        throwsA(isA<ModelConfigException>()),
      );
    });

    test('未知标签抛异常', () {
      final preprocess = {
        'input_size': [48, 48],
        'channels': 1,
        'output_classes': 7,
      };
      final labels = {
        'labels': [
          'angry', 'disgust', 'fear', 'happy',
          'neutral', 'sad', 'surprise',
          // 第 8 个未知
          'curious',
        ],
      };

      final config = ExpressionModelConfig.fromJson(
        preprocessJson: preprocess,
        labelsJson: labels,
      );

      // output_classes 默认 7,labels 有 8 个 -> 标签数不匹配
      expect(
        config.validate,
        throwsA(isA<ModelConfigException>()),
      );
    });

    test('合法配置 validate 通过', () {
      final config = ExpressionModelConfig.fer2013Default();
      expect(() => config.validate(), returnsNormally);
    });
  });

  group('ExpressionModelConfig - 索引映射', () {
    test('labelForIndex 按标签顺序映射到 ExpressionLabel', () {
      final config = ExpressionModelConfig.fer2013Default();

      expect(config.labelForIndex(0), ExpressionLabel.angry);
      expect(config.labelForIndex(1), ExpressionLabel.disgust);
      expect(config.labelForIndex(2), ExpressionLabel.fear);
      expect(config.labelForIndex(3), ExpressionLabel.happy);
      expect(config.labelForIndex(4), ExpressionLabel.neutral);
      expect(config.labelForIndex(5), ExpressionLabel.sad);
      expect(config.labelForIndex(6), ExpressionLabel.surprise);
    });

    test('labelForIndex 越界返回 unknown', () {
      final config = ExpressionModelConfig.fer2013Default();
      expect(config.labelForIndex(-1), ExpressionLabel.unknown);
      expect(config.labelForIndex(7), ExpressionLabel.unknown);
      expect(config.labelForIndex(99), ExpressionLabel.unknown);
    });
  });

  group('ExpressionModelConfig - FER2013 默认配置', () {
    test('fer2013Default 提供合理的兜底参数', () {
      final config = ExpressionModelConfig.fer2013Default();

      expect(config.inputHeight, 48);
      expect(config.inputWidth, 48);
      expect(config.channels, 1);
      expect(config.colorMode, 'grayscale');
      expect(config.outputClasses, 7);
      expect(config.outputFormat, 'softmax');
      expect(config.faceCropEnabled, isTrue);
      expect(config.faceCropPaddingRatio, 0.2);
      // 兜底配置不应被当作真实模型
      expect(config.modelVersion, 'fer2013-default-pending');
    });
  });

  group('ExpressionModelConfig - model_card.json SHA-256', () {
    test('model_card.json 提供的 sha256 写入 modelSha256', () {
      final preprocess = {
        'input_size': [48, 48],
        'channels': 1,
        'output_classes': 7,
      };
      final modelCard = {
        'sha256':
            'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2',
        'model_version': 'mobilenetv3-v1.0',
      };

      final config = ExpressionModelConfig.fromJson(
        preprocessJson: preprocess,
        modelCardJson: modelCard,
      );

      expect(config.modelSha256, startsWith('a1b2c3'));
      expect(config.modelVersion, 'mobilenetv3-v1.0');
    });
  });

  group('ExpressionNormalization - 归一化方法', () {
    test('divide_255: x / 255.0', () {
      const norm = ExpressionNormalization.divide255();
      expect(norm.apply(0, 0), 0.0);
      expect(norm.apply(255, 0), 1.0);
      expect(norm.apply(128, 0), closeTo(128 / 255, 1e-6));
    });

    test('standardize: (x/255 - mean) / std', () {
      const norm = ExpressionNormalization(
        method: 'standardize',
        mean: [0.5],
        std: [0.5],
      );
      // (255/255 - 0.5) / 0.5 = 1.0
      expect(norm.apply(255, 0), 1.0);
      // (0/255 - 0.5) / 0.5 = -1.0
      expect(norm.apply(0, 0), -1.0);
      // (128/255 - 0.5) / 0.5 ≈ 0.0039
      expect(norm.apply(128, 0), closeTo((128 / 255 - 0.5) / 0.5, 1e-6));
    });

    test('scale_only: x * scale', () {
      const norm = ExpressionNormalization(
        method: 'scale_only',
        scale: 0.00392156862, // 1/255
      );
      expect(norm.apply(255, 0), closeTo(1.0, 1e-6));
      expect(norm.apply(0, 0), 0.0);
    });

    test('none: 原值不变', () {
      const norm = ExpressionNormalization(method: 'none');
      expect(norm.apply(128, 0), 128.0);
    });
  });

  group('ExpressionModelConfig - loadFromAssets 失败行为', () {
    test('preprocess.json 缺失抛 ModelConfigException (不静默兜底)', () {
      // 指向不存在的子目录,模拟模型未安装的场景。
      // assets/models/ 下已存在真实 preprocess.json(由 cnn-training 分支提供),
      // 因此用一个不存在的 basePath 验证缺失时的错误处理。
      expect(
        () => ExpressionModelConfig.loadFromAssets(
          basePath: 'assets/models/_nonexistent_subdir',
        ),
        throwsA(isA<ModelConfigException>()),
      );
    });
  });

  group('ExpressionModelConfig - loadFromAssets 真实模型', () {
    test('assets/models/preprocess.json 加载成功并解析为 224x224x3 配置', () async {
      // 真实 FER2013 MobileNetV3-Small 模型已安装,
      // loadFromAssets 应成功返回与训练配置一致的参数。
      final config = await ExpressionModelConfig.loadFromAssets(
        basePath: 'assets/models',
      );

      expect(config.inputHeight, 224);
      expect(config.inputWidth, 224);
      expect(config.channels, 3);
      expect(config.colorMode, 'rgb');
      expect(config.outputClasses, 7);
      expect(config.outputFormat, 'logits');
      expect(config.labels.length, 7);
      expect(config.labels, [
        'angry',
        'disgust',
        'fear',
        'happy',
        'sad',
        'surprise',
        'neutral',
      ]);
      // model_card.json 提供 SHA-256
      expect(config.modelSha256, isNotNull);
      expect(config.modelSha256!.length, 64); // SHA-256 hex
    });
  });
}
