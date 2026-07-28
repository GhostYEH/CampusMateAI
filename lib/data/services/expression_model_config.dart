import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/foundation.dart' show FlutterError;
import 'package:flutter/services.dart' show rootBundle;

import '../models/expression.dart';

/// CNN 表情识别模型配置 — 由 cnn-training 分支提供的 JSON 文件加载。
///
/// 加载的文件:
/// - `assets/models/labels.json`: 七类表情标签顺序
/// - `assets/models/preprocess.json`: 预处理参数(输入尺寸/通道/归一化/缩放)
/// - `assets/models/model_card.json`(可选): SHA-256 / 张量说明 / 训练元数据
///
/// 文件格式(参考,cnn-training 分支应按此格式提供):
/// ```json
/// // labels.json
/// {
///   "labels": ["angry", "disgust", "fear", "happy", "neutral", "sad", "surprise"],
///   "version": "fer2013-v1.0"
/// }
///
/// // preprocess.json
/// {
///   "input_shape": [1, 48, 48, 1],
///   "input_size": [48, 48],
///   "channels": 1,
///   "color_mode": "grayscale",
///   "normalization": {
///     "method": "divide_255",
///     "mean": [0.5],
///     "std": [0.5]
///   },
///   "resize_method": "bilinear",
///   "face_crop": { "enabled": true, "padding_ratio": 0.2 },
///   "output_classes": 7,
///   "output_format": "softmax",
///   "model_version": "mobilenetv3-small-fer2013-v1.0"
/// }
/// ```
class ExpressionModelConfig {
  const ExpressionModelConfig({
    required this.labels,
    required this.inputHeight,
    required this.inputWidth,
    required this.channels,
    required this.colorMode,
    required this.normalization,
    required this.resizeMethod,
    required this.faceCropEnabled,
    required this.faceCropPaddingRatio,
    required this.outputClasses,
    required this.outputFormat,
    required this.modelVersion,
    this.modelSha256,
    this.tensorInputShape,
    this.tensorOutputShape,
  });

  /// 七类表情标签顺序(必须与模型输出维度一一对应)。
  ///
  /// FER2013 标准顺序: angry, disgust, fear, happy, neutral, sad, surprise
  /// 注意:本项目 `ExpressionLabel` 还包含 `unknown` 与 `noFace`,
  /// 但这两个不是 CNN 输出类别,由后处理根据置信度判断。
  final List<String> labels;

  /// 模型输入高度(像素)。
  final int inputHeight;

  /// 模型输入宽度(像素)。
  final int inputWidth;

  /// 模型输入通道数(1=灰度, 3=RGB)。
  final int channels;

  /// 颜色模式: 'grayscale' / 'rgb' / 'bgr'。
  final String colorMode;

  /// 归一化参数。
  final ExpressionNormalization normalization;

  /// 缩放方法: 'bilinear' / 'nearest' / 'area'。
  final String resizeMethod;

  /// 是否启用 ML Kit 人脸裁剪(裁剪到人脸边界框后再 resize)。
  final bool faceCropEnabled;

  /// 人脸裁剪边界框外扩比例(0.2 = 向外扩 20% 以包含下巴/额头)。
  final double faceCropPaddingRatio;

  /// 模型输出类别数(应为 7,FER2013 七类表情)。
  final int outputClasses;

  /// 输出格式: 'softmax' / 'logits' / 'sigmoid'。
  /// softmax: 概率分布,总和为 1
  /// logits: 原始输出,需手动 softmax
  /// sigmoid: 独立二分类(本项目不使用)
  final String outputFormat;

  /// 模型版本(用于 ExpressionResult.modelVersion)。
  final String modelVersion;

  /// 模型文件 SHA-256(可选,用于完整性校验与验收报告)。
  final String? modelSha256;

  /// TFLite 输入张量形状(如 [1, 48, 48, 1])。
  final List<int>? tensorInputShape;

  /// TFLite 输出张量形状(如 [1, 7])。
  final List<int>? tensorOutputShape;

  /// FER2013 默认配置(cnn-training 分支未提供 preprocess.json 时的兜底)。
  ///
  /// 兜底策略:48x48 灰度,/255.0 归一化,七类 softmax 输出。
  /// **注意**:这是兜底,实际应使用 cnn-training 分支提供的 preprocess.json。
  factory ExpressionModelConfig.fer2013Default() {
    return const ExpressionModelConfig(
      labels: ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise'],
      inputHeight: 48,
      inputWidth: 48,
      channels: 1,
      colorMode: 'grayscale',
      normalization: ExpressionNormalization.divide255(),
      resizeMethod: 'bilinear',
      faceCropEnabled: true,
      faceCropPaddingRatio: 0.2,
      outputClasses: 7,
      outputFormat: 'softmax',
      modelVersion: 'fer2013-default-pending',
    );
  }

  /// 从 JSON 解析配置。
  ///
  /// [preprocessJson] 为 preprocess.json 的解析结果。
  /// [labelsJson] 为 labels.json 的解析结果(可选,缺省时使用 FER2013 标准顺序)。
  /// [modelCardJson] 为 model_card.json 的解析结果(可选)。
  factory ExpressionModelConfig.fromJson({
    required Map<String, dynamic> preprocessJson,
    Map<String, dynamic>? labelsJson,
    Map<String, dynamic>? modelCardJson,
  }) {
    final inputShape = (preprocessJson['input_shape'] as List?)
            ?.map((e) => (e as num).toInt())
            .toList() ??
        [1, 48, 48, 1];
    final inputSize = (preprocessJson['input_size'] as List?)
            ?.map((e) => (e as num).toInt())
            .toList() ??
        [inputShape.length >= 3 ? inputShape[1] : 48,
         inputShape.length >= 3 ? inputShape[2] : 48,];
    final channels = (preprocessJson['channels'] as num?)?.toInt() ??
        (inputShape.length >= 4 ? inputShape[3] : 1);
    final colorMode = (preprocessJson['color_mode'] as String?) ?? 'grayscale';
    final resizeMethod =
        (preprocessJson['resize_method'] as String?) ?? 'bilinear';
    final faceCrop = preprocessJson['face_crop'] as Map<String, dynamic>?;
    final outputClasses = (preprocessJson['output_classes'] as num?)?.toInt() ?? 7;
    final outputFormat =
        (preprocessJson['output_format'] as String?) ?? 'softmax';
    final modelVersion = (preprocessJson['model_version'] as String?) ??
        (modelCardJson?['model_version'] as String?) ??
        'unknown';

    final labels = (labelsJson?['labels'] as List?)
            ?.map((e) => e.toString())
            .toList() ??
        const ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise'];

    final normJson =
        preprocessJson['normalization'] as Map<String, dynamic>? ?? {};
    final normMethod = (normJson['method'] as String?) ?? 'divide_255';
    final meanList = (normJson['mean'] as List?)
        ?.map((e) => (e as num).toDouble())
        .toList();
    final stdList = (normJson['std'] as List?)
        ?.map((e) => (e as num).toDouble())
        .toList();
    final scale = (normJson['scale'] as num?)?.toDouble() ?? 1.0;

    final normalization = ExpressionNormalization(
      method: normMethod,
      mean: meanList ?? const [],
      std: stdList ?? const [],
      scale: scale,
    );

    return ExpressionModelConfig(
      labels: List.unmodifiable(labels),
      inputHeight: inputSize[0],
      inputWidth: inputSize[1],
      channels: channels,
      colorMode: colorMode,
      normalization: normalization,
      resizeMethod: resizeMethod,
      faceCropEnabled: (faceCrop?['enabled'] as bool?) ?? true,
      faceCropPaddingRatio:
          (faceCrop?['padding_ratio'] as num?)?.toDouble() ?? 0.2,
      outputClasses: outputClasses,
      outputFormat: outputFormat,
      modelVersion: modelVersion,
      modelSha256: modelCardJson?['sha256'] as String?,
      tensorInputShape: inputShape,
      tensorOutputShape: (preprocessJson['output_shape'] as List?)
          ?.map((e) => (e as num).toInt())
          .toList(),
    );
  }

  /// 从 assets 加载完整配置。
  ///
  /// 加载顺序:
  /// 1. `assets/models/preprocess.json`(必需)
  /// 2. `assets/models/labels.json`(可选,缺省时使用 FER2013 标准顺序)
  /// 3. `assets/models/model_card.json`(可选,提供 SHA-256)
  ///
  /// **失败行为**:
  /// - preprocess.json 缺失 → 抛出 [ModelConfigException]
  /// - JSON 解析失败 → 抛出 [ModelConfigException]
  /// - 标签数与 output_classes 不匹配 → 抛出 [ModelConfigException]
  static Future<ExpressionModelConfig> loadFromAssets({
    String basePath = 'assets/models',
  }) async {
    final preprocessStr = await _safeLoadAsset('$basePath/preprocess.json');
    if (preprocessStr == null) {
      throw const ModelConfigException(
        'preprocess.json 未找到。请等待 cnn-training 分支提供模型配置文件,'
        '放入 assets/models/ 后重新构建应用。',
      );
    }
    Map<String, dynamic> preprocessJson;
    try {
      preprocessJson = jsonDecode(preprocessStr) as Map<String, dynamic>;
    } catch (e) {
      throw ModelConfigException('preprocess.json 解析失败: $e');
    }

    Map<String, dynamic>? labelsJson;
    final labelsStr = await _safeLoadAsset('$basePath/labels.json');
    if (labelsStr != null) {
      try {
        labelsJson = jsonDecode(labelsStr) as Map<String, dynamic>;
      } catch (e) {
        throw ModelConfigException('labels.json 解析失败: $e');
      }
    }

    Map<String, dynamic>? modelCardJson;
    final modelCardStr = await _safeLoadAsset('$basePath/model_card.json');
    if (modelCardStr != null) {
      try {
        modelCardJson = jsonDecode(modelCardStr) as Map<String, dynamic>;
      } catch (_) {
        // model_card.json 解析失败不影响主流程
      }
    }

    final config = ExpressionModelConfig.fromJson(
      preprocessJson: preprocessJson,
      labelsJson: labelsJson,
      modelCardJson: modelCardJson,
    );
    config.validate();
    return config;
  }

  /// 校验配置一致性(标签数 == output_classes,通道数合法等)。
  ///
  /// 校验失败抛出 [ModelConfigException]。
  void validate() {
    if (labels.length != outputClasses) {
      throw ModelConfigException(
        '标签数(${labels.length})与 output_classes($outputClasses)不匹配。'
        'labels: $labels',
      );
    }
    if (outputClasses != 7) {
      throw ModelConfigException(
        '本项目仅支持 7 类表情(FER2013),当前 output_classes=$outputClasses。'
        '若使用其他类别数,需修改 ExpressionLabel 枚举与 UI 文案。',
      );
    }
    if (channels != 1 && channels != 3) {
      throw ModelConfigException(
        'channels 必须为 1(灰度)或 3(RGB),当前 channels=$channels。',
      );
    }
    if (inputHeight <= 0 || inputWidth <= 0) {
      throw ModelConfigException(
        'input_size 必须为正,当前 ${inputHeight}x$inputWidth。',
      );
    }
    for (final label in labels) {
      if (!_isKnownLabel(label)) {
        throw ModelConfigException(
          "未知标签 '$label'。期望为 FER2013 七类之一: "
          'angry, disgust, fear, happy, neutral, sad, surprise。',
        );
      }
    }
  }

  bool _isKnownLabel(String label) {
    const known = {
      'angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise',
      // 兼容下划线/连字符变体
      'angry_', 'disgust_', 'fear_', 'happy_', 'neutral_', 'sad_', 'surprise_',
    };
    final normalized = label.toLowerCase().replaceAll('-', '').replaceAll('_', '');
    return known.any((k) => k.replaceAll('_', '') == normalized);
  }

  /// 将模型输出索引映射到 [ExpressionLabel]。
  ///
  /// 索引顺序由 [labels] 决定,与模型输出维度一一对应。
  ExpressionLabel labelForIndex(int index) {
    if (index < 0 || index >= labels.length) return ExpressionLabel.unknown;
    return ExpressionLabel.fromString(labels[index]);
  }

  @override
  String toString() =>
      'ExpressionModelConfig(modelVersion=$modelVersion, '
      'input=${inputHeight}x${inputWidth}x$channels, '
      'labels=$labels, outputClasses=$outputClasses, '
      'sha256=${modelSha256?.substring(0, 12) ?? "n/a"}...)';
}

/// 归一化参数。
class ExpressionNormalization {
  const ExpressionNormalization({
    required this.method,
    this.mean = const [],
    this.std = const [],
    this.scale = 1.0,
  });

  /// 归一化方法:
  /// - 'divide_255': x / 255.0
  /// - 'standardize': (x / 255.0 - mean) / std
  /// - 'scale_only': x * scale
  /// - 'none': 不归一化
  final String method;
  final List<double> mean;
  final List<double> std;
  final double scale;

  /// /255.0 归一化(FER2013 常用)。
  const factory ExpressionNormalization.divide255() =
      ExpressionNormalization._divide255;

  const ExpressionNormalization._divide255()
      : method = 'divide_255',
        mean = const [],
        std = const [],
        scale = 1.0;

  /// 对单通道像素值应用归一化,返回 float 值。
  ///
  /// [pixel] 为 0~255 的像素值。
  /// [channelIndex] 为通道索引(用于多通道 mean/std)。
  double apply(int pixel, int channelIndex) {
    switch (method) {
      case 'divide_255':
        return pixel / 255.0;
      case 'standardize':
        final m = channelIndex < mean.length ? mean[channelIndex] : 0.0;
        final s = channelIndex < std.length && std[channelIndex] > 0
            ? std[channelIndex]
            : 1.0;
        return (pixel / 255.0 - m) / s;
      case 'scale_only':
        return pixel * scale;
      case 'none':
      default:
        return pixel.toDouble();
    }
  }
}

/// 模型配置异常。
class ModelConfigException implements Exception {
  const ModelConfigException(this.message);
  final String message;

  @override
  String toString() => 'ModelConfigException: $message';
}

/// 加载 asset,文件不存在时返回 null(不抛异常)。
Future<String?> _safeLoadAsset(String path) async {
  try {
    return await rootBundle.loadString(path);
  } on FlutterError {
    return null;
  } on Exception {
    return null;
  }
}

/// 加载 TFLite 模型字节。
///
/// 与 [ExpressionModelConfig.loadFromAssets] 分离,因为模型文件较大,
/// 需要单独加载并可能进行 SHA-256 校验。
///
/// 失败行为:
/// - 文件缺失 → 返回 null(调用方决定是否报错)
/// - 加载异常 → 重新抛出
Future<Uint8List?> loadModelBytes(String path) async {
  try {
    final byteData = await rootBundle.load(path);
    return byteData.buffer.asUint8List();
  } on FlutterError {
    return null;
  } on Exception {
    return null;
  }
}
