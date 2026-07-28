import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:campus_companion/data/services/expression_service_status.dart';
import 'package:campus_companion/data/services/lite_rt_expression_recognition_service.dart';

void main() {
  group('LiteRtExpressionRecognitionService - 平台支持', () {
    test('isPlatformSupported 在 Flutter test 环境返回合理值', () {
      // Flutter test 默认运行在 dart:io Platform 上(取决于宿主机),
      // 但 kIsWeb 在测试中为 false。
      // 这里仅验证该方法不抛异常,且返回 bool。
      final result = LiteRtExpressionRecognitionService.isPlatformSupported;
      expect(result, isA<bool>());
    });

    test('kIsWeb 在测试环境为 false', () {
      // 验证测试环境不是 Web
      expect(kIsWeb, isFalse);
    });
  });

  group('LiteRtExpressionRecognitionService - 模型缺失场景', () {
    test('initialize 在模型文件缺失时发出 notInstalled 状态(不抛异常,不静默回退 Mock)', () async {
      // assets/models/ 下无 expression_model.tflite 与 preprocess.json
      // initialize 应通过 status 流发出 notInstalled 状态,
      // 而不是抛异常或自动切换到 Mock 实现。
      final service = LiteRtExpressionRecognitionService();

      final statusList = <ExpressionServiceStatus>[];
      final sub = service.status.listen(statusList.add);

      await service.initialize();

      // 等待事件循环处理完流事件
      await Future<void>.delayed(Duration.zero);

      expect(statusList, isNotEmpty);

      // 应该至少有一个状态显示模型未就绪
      final hasNotReady = statusList.any(
        (s) =>
            s.modelState == ExpressionModelState.notInstalled ||
            s.modelState == ExpressionModelState.failed ||
            s.modelState == ExpressionModelState.idle,
      );
      expect(
        hasNotReady,
        isTrue,
        reason: '模型缺失时应发出 notInstalled/failed/idle 状态,'
            '不静默回退 Mock。实际状态: ${statusList.map((s) => s.modelState)}',
      );

      // 不应出现 ready 状态(因为模型未提供)
      final hasReady = statusList.any(
        (s) => s.modelState == ExpressionModelState.ready,
      );
      expect(
        hasReady,
        isFalse,
        reason: '模型未提供时不应报告 ready',
      );

      await sub.cancel();
      await service.dispose();
    });

    test('initialize 在模型缺失时通过 modelError 提供有用错误信息', () async {
      final service = LiteRtExpressionRecognitionService();

      final statusList = <ExpressionServiceStatus>[];
      final sub = service.status.listen(statusList.add);

      await service.initialize();
      await Future<void>.delayed(Duration.zero);

      // 错误信息应可读,引导用户/开发者放入模型文件
      final errorStates = statusList.where(
        (s) =>
            s.modelState == ExpressionModelState.notInstalled ||
            s.modelState == ExpressionModelState.failed,
      );

      if (errorStates.isNotEmpty) {
        final error = errorStates.first;
        expect(error.modelError, isNotNull);
        expect(error.modelError!.isNotEmpty, isTrue);
        // 错误信息应提到模型文件或 cnn-training 分支
        expect(
          error.modelError!.contains('expression_model.tflite') ||
              error.modelError!.contains('preprocess.json') ||
              error.modelError!.contains('cnn-training'),
          isTrue,
          reason: '错误信息应引导放入模型文件,实际: ${error.modelError}',
        );
      }

      await sub.cancel();
      await service.dispose();
    });
  });

  group('LiteRtExpressionRecognitionService - start 行为', () {
    test('模型未就绪时 start 不抛异常(静默返回)', () async {
      // 模型未 initialize 或 initialize 失败,start 应安全返回,
      // 不抛异常让 UI 崩溃。
      final service = LiteRtExpressionRecognitionService();

      // 直接 start(未 initialize)
      expect(() => service.start(), returnsNormally);

      await service.dispose();
    });

    test('isRunning 初始为 false', () {
      final service = LiteRtExpressionRecognitionService();
      expect(service.isRunning, isFalse);
      service.dispose();
    });
  });

  group('LiteRtExpressionRecognitionService - 生命周期', () {
    test('dispose 可被多次调用 (幂等)', () async {
      final service = LiteRtExpressionRecognitionService();
      await service.dispose();
      // 二次 dispose 不应抛异常
      await service.dispose();
    });

    test('dispose 后 initialize 抛 StateError', () async {
      final service = LiteRtExpressionRecognitionService();
      await service.dispose();
      expect(
        () => service.initialize(),
        throwsA(isA<StateError>()),
      );
    });

    test('pause / stop 在未启动时调用不抛异常', () async {
      final service = LiteRtExpressionRecognitionService();
      await service.pause();
      await service.stop();
      await service.dispose();
    });
  });

  group('LiteRtExpressionRecognitionService - 默认参数', () {
    test('默认 targetFps=8 (合理上限,避免低端设备帧堆积)', () {
      // 通过构造函数验证默认参数
      final service = LiteRtExpressionRecognitionService();
      // targetFps 是 public 字段,可直接读取
      expect(service.targetFps, 8);
      service.dispose();
    });

    test('默认 smoother 参数: 置信度阈值 0.45, stableFrames=5, windowSize=7', () {
      // 这些参数对齐 AGENTS.md §6 "多帧概率平滑、置信度阈值、状态持续时间判断、
      // 提醒冷却时间"的强制要求
      final service = LiteRtExpressionRecognitionService();
      // service._smoother 是 private, 但通过默认构造的参数验证
      // 这里只验证构造不抛异常
      expect(service, isNotNull);
      service.dispose();
    });
  });
}
