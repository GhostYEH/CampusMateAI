import '../../data/models/expression.dart';

/// 表情多帧平滑器。
///
/// 解决问题:CNN 单帧结果在不同类别间瞬间跳变,体验差且不稳定。
/// 策略:
/// 1. 滑动窗口平均概率分布,降低单帧抖动;
/// 2. 连续 [stableFrames] 帧最大类别一致才标记为 stable;
/// 3. 置信度低于 [confidenceThreshold] 标记为低置信度,isStable=false,
///    且不触发情绪安慰。
///
/// 该类纯逻辑、无副作用,便于单元测试。
class ExpressionSmoother {
  ExpressionSmoother({
    required this.confidenceThreshold,
    required this.stableFrames,
    this.windowSize = 7,
  })  : assert(confidenceThreshold >= 0 && confidenceThreshold <= 1),
        assert(stableFrames > 0),
        assert(windowSize > 0);

  final double confidenceThreshold;
  final int stableFrames;
  final int windowSize;

  final List<Map<ExpressionLabel, double>> _window = [];
  ExpressionLabel _lastStableLabel = ExpressionLabel.unknown;
  int _stableStreak = 0;

  /// 输入一帧原始概率,输出平滑后的结果。
  ExpressionResult smooth(
    Map<ExpressionLabel, double> rawProbabilities,
    DateTime timestamp, {
    String modelVersion = 'mock-v0.1',
  }) {
    _window.add(rawProbabilities);
    if (_window.length > windowSize) {
      _window.removeRange(0, _window.length - windowSize);
    }

    final averaged = _average(_window);
    final top = _topEntry(averaged);
    final label = top.key;
    final confidence = top.value;

    // 稳定性判断:连续 N 帧同一类别 & 置信度达标
    if (label == _lastStableLabel && confidence >= confidenceThreshold) {
      _stableStreak++;
    } else if (confidence >= confidenceThreshold) {
      _stableStreak = 1;
      _lastStableLabel = label;
    } else {
      // 低置信度时重置稳定计数,不更新稳定标签
      _stableStreak = 0;
    }

    final isStable = _stableStreak >= stableFrames;

    return ExpressionResult(
      label: label,
      confidence: confidence,
      probabilities: averaged,
      timestamp: timestamp,
      isStable: isStable,
      modelVersion: modelVersion,
    );
  }

  /// 重置状态(新一轮识别)。
  void reset() {
    _window.clear();
    _lastStableLabel = ExpressionLabel.unknown;
    _stableStreak = 0;
  }

  Map<ExpressionLabel, double> _average(
    List<Map<ExpressionLabel, double>> samples,
  ) {
    if (samples.isEmpty) {
      return {for (final l in ExpressionLabel.values) l: 0};
    }
    final sums = <ExpressionLabel, double>{
      for (final l in ExpressionLabel.values) l: 0,
    };
    for (final sample in samples) {
      for (final entry in sample.entries) {
        sums[entry.key] = (sums[entry.key] ?? 0) + entry.value;
      }
    }
    final n = samples.length;
    return {for (final e in sums.entries) e.key: e.value / n};
  }

  MapEntry<ExpressionLabel, double> _topEntry(
    Map<ExpressionLabel, double> probabilities,
  ) {
    ExpressionLabel label = ExpressionLabel.noFace;
    double max = -1;
    probabilities.forEach((k, v) {
      if (v > max) {
        max = v;
        label = k;
      }
    });
    // 如果最大值仍为0,说明未检测到人脸
    if (max <= 0) return const MapEntry(ExpressionLabel.noFace, 0);
    return MapEntry(label, max);
  }
}

/// 建议冷却计时器 — 防止短时间内反复弹出陪伴建议。
class SuggestionCooldown {
  SuggestionCooldown({required this.cooldownMinutes})
      : assert(cooldownMinutes >= 0);

  final int cooldownMinutes;
  DateTime? _lastTriggered;

  /// 是否可以触发(冷却已过)。
  bool canTrigger({DateTime? now}) {
    final reference = now ?? DateTime.now();
    if (_lastTriggered == null) return true;
    return reference.difference(_lastTriggered!).inMinutes >= cooldownMinutes;
  }

  /// 记录一次触发。
  void markTriggered({DateTime? now}) {
    _lastTriggered = now ?? DateTime.now();
  }

  /// 剩余冷却秒数(0 表示可触发)。
  int remainingSeconds({DateTime? now}) {
    final reference = now ?? DateTime.now();
    if (_lastTriggered == null) return 0;
    final elapsed = reference.difference(_lastTriggered!);
    final total = cooldownMinutes * 60;
    final remaining = total - elapsed.inSeconds;
    return remaining < 0 ? 0 : remaining;
  }

  void reset() => _lastTriggered = null;
}
