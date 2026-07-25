import 'package:equatable/equatable.dart';

/// 表情识别标签 — 对应 FER2013 类别 + 工程扩展。
///
/// 科学边界说明: 该标签仅描述"可观察到的面部表情",
/// 不代表心理诊断或情绪判定。详见 AGENTS.md §3。
enum ExpressionLabel {
  happy('开心'),
  neutral('中性'),
  sad('低落'),
  angry('愤怒'),
  fear('恐惧'),
  surprise('惊讶'),
  disgust('厌恶'),
  unknown('未识别'),
  noFace('未检测到人脸');

  const ExpressionLabel(this.displayName);
  final String displayName;

  String get name => toString().split('.').last;

  static ExpressionLabel fromString(String? value) {
    if (value == null) return ExpressionLabel.unknown;
    final v = value.toLowerCase().replaceAll('_', '').replaceAll('-', '');
    for (final label in ExpressionLabel.values) {
      if (label.name.toLowerCase() == v) return label;
    }
    switch (v) {
      case 'noface':
        return ExpressionLabel.noFace;
      default:
        return ExpressionLabel.unknown;
    }
  }
}

/// 单帧表情识别结果。
///
/// [isStable] 表示该结果已经过多帧平滑,可作为稳定输出使用。
/// [modelVersion] 标注来源模型,Mock 阶段固定为 "mock-v0.1"。
class ExpressionResult extends Equatable {
  const ExpressionResult({
    required this.label,
    required this.confidence,
    required this.probabilities,
    required this.timestamp,
    required this.isStable,
    required this.modelVersion,
  });

  final ExpressionLabel label;
  final double confidence; // 0.0 ~ 1.0
  final Map<ExpressionLabel, double> probabilities;
  final DateTime timestamp;
  final bool isStable;
  final String modelVersion;

  /// 是否属于低置信度(低于阈值),此时不应触发情绪安慰。
  bool get isLowConfidence =>
      confidence < 0.45 || label == ExpressionLabel.unknown;

  bool get hasFace => label != ExpressionLabel.noFace;

  /// 排序后的概率分布(用于可视化)
  List<MapEntry<ExpressionLabel, double>> get sortedProbabilities {
    final entries = probabilities.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    return entries;
  }

  ExpressionResult copyWith({
    ExpressionLabel? label,
    double? confidence,
    Map<ExpressionLabel, double>? probabilities,
    DateTime? timestamp,
    bool? isStable,
    String? modelVersion,
  }) {
    return ExpressionResult(
      label: label ?? this.label,
      confidence: confidence ?? this.confidence,
      probabilities: probabilities ?? this.probabilities,
      timestamp: timestamp ?? this.timestamp,
      isStable: isStable ?? this.isStable,
      modelVersion: modelVersion ?? this.modelVersion,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'label': label.name,
      'confidence': confidence,
      'probabilities': {
        for (final e in probabilities.entries) e.key.name: e.value,
      },
      'timestamp': timestamp.toIso8601String(),
      'isStable': isStable,
      'modelVersion': modelVersion,
    };
  }

  factory ExpressionResult.fromJson(Map<String, dynamic> json) {
    final probsRaw = (json['probabilities'] as Map<String, dynamic>?) ?? {};
    return ExpressionResult(
      label: ExpressionLabel.fromString(json['label'] as String?),
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
      probabilities: {
        for (final entry in probsRaw.entries)
          ExpressionLabel.fromString(entry.key):
              (entry.value as num).toDouble(),
      },
      timestamp: DateTime.tryParse(json['timestamp'] as String? ?? '') ??
          DateTime.now(),
      isStable: json['isStable'] as bool? ?? false,
      modelVersion: json['modelVersion'] as String? ?? 'unknown',
    );
  }

  @override
  List<Object?> get props =>
      [label, confidence, probabilities, timestamp, isStable, modelVersion];
}
