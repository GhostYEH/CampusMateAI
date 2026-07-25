import 'package:flutter_test/flutter_test.dart';
import 'package:campus_companion/data/models/expression.dart';
import 'package:campus_companion/mock/mock_services/expression_smoother.dart';

/// 构造单峰概率分布: 指定标签占主,其他均分剩余。
Map<ExpressionLabel, double> _probs(
  ExpressionLabel main, {
  double mainConfidence = 0.8,
}) {
  final others = ExpressionLabel.values.where((l) => l != main).toList();
  final rest = (1 - mainConfidence) / others.length;
  return {
    for (final l in ExpressionLabel.values)
      l: l == main ? mainConfidence : rest,
  };
}

/// 全零概率(模拟未检测到人脸)。
Map<ExpressionLabel, double> _zero() {
  return {for (final l in ExpressionLabel.values) l: 0};
}

void main() {
  group('ExpressionSmoother - 基本平滑', () {
    test('首帧不标记为 stable', () {
      final s = ExpressionSmoother(
        confidenceThreshold: 0.5,
        stableFrames: 3,
      );
      final r = s.smooth(_probs(ExpressionLabel.happy), DateTime.now());
      expect(r.label, ExpressionLabel.happy);
      expect(r.confidence, greaterThan(0.5));
      expect(r.isStable, isFalse);
    });

    test('连续 stableFrames 帧同类别且置信度达标后标记 stable', () {
      final s = ExpressionSmoother(
        confidenceThreshold: 0.5,
        stableFrames: 3,
      );
      final t0 = DateTime(2025, 1, 1, 10, 0);
      var r = s.smooth(_probs(ExpressionLabel.happy), t0);
      expect(r.isStable, isFalse); // streak=1
      r = s.smooth(
        _probs(ExpressionLabel.happy),
        t0.add(const Duration(seconds: 1)),
      );
      expect(r.isStable, isFalse); // streak=2
      r = s.smooth(
        _probs(ExpressionLabel.happy),
        t0.add(const Duration(seconds: 2)),
      );
      expect(r.isStable, isTrue); // streak=3 >= stableFrames
    });

    test('窗口平均: 单帧抖动不会立即改变主标签', () {
      final s = ExpressionSmoother(
        confidenceThreshold: 0.4,
        stableFrames: 2,
        windowSize: 5,
      );
      final t0 = DateTime(2025, 1, 1, 10, 0);
      // 4 帧 happy(高置信度)
      for (var i = 0; i < 4; i++) {
        s.smooth(
          _probs(ExpressionLabel.happy, mainConfidence: 0.9),
          t0.add(Duration(seconds: i)),
        );
      }
      // 1 帧 sad 注入(单帧抖动), 窗口内仍是 happy 主导
      final r = s.smooth(
        _probs(ExpressionLabel.sad, mainConfidence: 0.7),
        t0.add(const Duration(seconds: 4)),
      );
      // 由于窗口平均,4 帧 happy vs 1 帧 sad,平均后 happy 仍最高
      expect(r.label, ExpressionLabel.happy);
    });
  });

  group('ExpressionSmoother - 低置信度处理', () {
    test('置信度低于阈值时不标记 stable', () {
      final s = ExpressionSmoother(
        confidenceThreshold: 0.6,
        stableFrames: 2,
      );
      final t0 = DateTime(2025, 1, 1, 10, 0);
      // 多个标签平均分布 => 置信度低
      final lowConf = <ExpressionLabel, double>{
        for (final l in ExpressionLabel.values)
          l: 1 / ExpressionLabel.values.length,
      };
      var r = ExpressionResult(
        label: ExpressionLabel.unknown,
        confidence: 0,
        probabilities: const {},
        timestamp: DateTime.fromMillisecondsSinceEpoch(0),
        isStable: true,
        modelVersion: 'test',
      );
      for (var i = 0; i < 5; i++) {
        r = s.smooth(lowConf, t0.add(Duration(seconds: i)));
      }
      // 平均分布时最大值约 1/9 ≈ 0.11, 远低于阈值 0.6
      expect(r.confidence, lessThan(0.6));
      expect(r.isStable, isFalse);
      expect(r.isLowConfidence, isTrue);
    });

    test('低置信度重置稳定计数,后续需重新积累', () {
      // 阈值较高(0.7),使单帧低置信度足以把窗口平均拖到阈值以下
      final s = ExpressionSmoother(
        confidenceThreshold: 0.7,
        stableFrames: 3,
      );
      final t0 = DateTime(2025, 1, 1, 10, 0);
      // 2 帧 happy (streak=2, 未达 stable)
      s.smooth(_probs(ExpressionLabel.happy, mainConfidence: 0.9), t0);
      s.smooth(
        _probs(ExpressionLabel.happy, mainConfidence: 0.9),
        t0.add(const Duration(seconds: 1)),
      );
      // 1 帧低置信度(均匀分布)→ happy 平均 = (0.9+0.9+0.111)/3 ≈ 0.637 < 0.7,重置 streak
      final lowConf = <ExpressionLabel, double>{
        for (final l in ExpressionLabel.values)
          l: 1 / ExpressionLabel.values.length,
      };
      s.smooth(lowConf, t0.add(const Duration(seconds: 2)));
      // 再 1 帧 happy → 平均仍可能 < 0.7,streak 重置后即使置信度达标也是 1
      final r = s.smooth(
        _probs(ExpressionLabel.happy, mainConfidence: 0.9),
        t0.add(const Duration(seconds: 3)),
      );
      // streak 至多为 1,不应 stable
      expect(r.isStable, isFalse);
    });

    test('ExpressionResult.isLowConfidence 阈值判定', () {
      final r1 = ExpressionResult(
        label: ExpressionLabel.happy,
        confidence: 0.3,
        probabilities: const {},
        timestamp: DateTime.now(),
        isStable: false,
        modelVersion: 'test',
      );
      expect(r1.isLowConfidence, isTrue); // 0.3 < 0.45

      final r2 = ExpressionResult(
        label: ExpressionLabel.happy,
        confidence: 0.7,
        probabilities: const {},
        timestamp: DateTime.now(),
        isStable: false,
        modelVersion: 'test',
      );
      expect(r2.isLowConfidence, isFalse);

      final r3 = ExpressionResult(
        label: ExpressionLabel.unknown,
        confidence: 0.9, // 即使置信度高,unknown 也是低置信度
        probabilities: const {},
        timestamp: DateTime.now(),
        isStable: false,
        modelVersion: 'test',
      );
      expect(r3.isLowConfidence, isTrue);
    });
  });

  group('ExpressionSmoother - 未检测到人脸', () {
    test('全零概率分布返回 noFace 标签', () {
      final s = ExpressionSmoother(
        confidenceThreshold: 0.5,
        stableFrames: 2,
      );
      final r = s.smooth(_zero(), DateTime.now());
      expect(r.label, ExpressionLabel.noFace);
      expect(r.hasFace, isFalse);
      expect(r.confidence, 0);
    });

    test('noFace 结果 hasFace=false, 不触发情绪安慰判定', () {
      final r = ExpressionResult(
        label: ExpressionLabel.noFace,
        confidence: 0,
        probabilities: const {},
        timestamp: DateTime.now(),
        isStable: true,
        modelVersion: 'test',
      );
      expect(r.hasFace, isFalse);
    });
  });

  group('ExpressionSmoother - 窗口溢出', () {
    test('窗口大小限制: 超出后仅保留最近 windowSize 帧', () {
      final s = ExpressionSmoother(
        confidenceThreshold: 0.5,
        stableFrames: 2,
        windowSize: 3,
      );
      final t0 = DateTime(2025, 1, 1, 10, 0);
      // 5 帧 happy, 窗口仅保留最近 3 帧
      for (var i = 0; i < 5; i++) {
        s.smooth(
          _probs(ExpressionLabel.happy, mainConfidence: 0.9),
          t0.add(Duration(seconds: i)),
        );
      }
      // 注入 1 帧 sad, 由于窗口大小=3, 包含 2 帧 happy + 1 帧 sad
      // happy 概率 = 0.9 * 2/3 + sad_rest * 2/3
      // sad 概率 = 0.7 * 1/3 + happy_rest * 1/3
      // happy 仍然占主导
      final r = s.smooth(
        _probs(ExpressionLabel.sad, mainConfidence: 0.7),
        t0.add(const Duration(seconds: 5)),
      );
      // 窗口为 [happy, happy, sad](前2帧已淘汰),happy 主导
      expect(r.label, ExpressionLabel.happy);
    });
  });

  group('ExpressionSmoother - reset', () {
    test('reset 清空窗口与稳定计数', () {
      final s = ExpressionSmoother(
        confidenceThreshold: 0.5,
        stableFrames: 2,
      );
      final t0 = DateTime(2025, 1, 1, 10, 0);
      s.smooth(_probs(ExpressionLabel.happy), t0);
      s.smooth(
        _probs(ExpressionLabel.happy),
        t0.add(const Duration(seconds: 1)),
      );
      s.reset();
      // reset 后第一帧应不 stable
      final r = s.smooth(
        _probs(ExpressionLabel.happy),
        t0.add(const Duration(seconds: 2)),
      );
      expect(r.isStable, isFalse);
    });
  });

  group('ExpressionSmoother - 标签切换稳定性', () {
    test('标签切换需重新积累 stableFrames 才标记 stable', () {
      // 使用小窗口(3)使标签切换更可预测
      final s = ExpressionSmoother(
        confidenceThreshold: 0.5,
        stableFrames: 3,
        windowSize: 3,
      );
      final t0 = DateTime(2025, 1, 1, 10, 0);
      // 4 帧 happy => stable (streak=3+)
      for (var i = 0; i < 4; i++) {
        s.smooth(
          _probs(ExpressionLabel.happy, mainConfidence: 0.9),
          t0.add(Duration(seconds: i)),
        );
      }
      // 切到 neutral: 需 2 帧让 neutral 在窗口(3)中占多数
      // 帧 4: 窗口=[h,h,n], happy 主导, streak 继续
      s.smooth(
        _probs(ExpressionLabel.neutral, mainConfidence: 0.9),
        t0.add(const Duration(seconds: 4)),
      );
      // 帧 5: 窗口=[h,n,n], neutral 主导, label 切换, streak 重置为 1
      var r = s.smooth(
        _probs(ExpressionLabel.neutral, mainConfidence: 0.9),
        t0.add(const Duration(seconds: 5)),
      );
      expect(r.label, ExpressionLabel.neutral);
      expect(r.isStable, isFalse); // streak=1 < 3

      // 帧 6: 窗口=[n,n,n], streak=2, 仍未 stable
      r = s.smooth(
        _probs(ExpressionLabel.neutral, mainConfidence: 0.9),
        t0.add(const Duration(seconds: 6)),
      );
      expect(r.isStable, isFalse); // streak=2 < 3

      // 帧 7: 窗口=[n,n,n], streak=3, stable
      r = s.smooth(
        _probs(ExpressionLabel.neutral, mainConfidence: 0.9),
        t0.add(const Duration(seconds: 7)),
      );
      expect(r.isStable, isTrue); // streak=3 >= 3
    });
  });

  group('ExpressionSmoother - 参数断言', () {
    test('stableFrames 必须 > 0', () {
      expect(
        () => ExpressionSmoother(confidenceThreshold: 0.5, stableFrames: 0),
        throwsA(isA<AssertionError>()),
      );
    });

    test('windowSize 必须 > 0', () {
      expect(
        () => ExpressionSmoother(
          confidenceThreshold: 0.5,
          stableFrames: 1,
          windowSize: 0,
        ),
        throwsA(isA<AssertionError>()),
      );
    });

    test('confidenceThreshold 必须在 [0,1]', () {
      expect(
        () => ExpressionSmoother(confidenceThreshold: -0.1, stableFrames: 1),
        throwsA(isA<AssertionError>()),
      );
      expect(
        () => ExpressionSmoother(confidenceThreshold: 1.5, stableFrames: 1),
        throwsA(isA<AssertionError>()),
      );
    });
  });
}
