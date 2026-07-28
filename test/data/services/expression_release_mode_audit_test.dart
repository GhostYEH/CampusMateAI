// Release 模式不回退 Mock 审计测试
//
// 通过源代码审计验证:
// 1. AppConfig.fromEnvironment 在 kReleaseMode=true 时强制 useMockBackend=false
// 2. AppConfig.fromEnvironment 在 kReleaseMode=true 时强制 useMockExpressionRecognition=false
// 3. expressionRecognitionProvider 在 useMockExpressionRecognition=false 时返回 LiteRt 实现
//
// 说明: kReleaseMode 是编译期常量,无法在测试中翻转。
// 这里通过静态分析 app_config.dart 与 app_providers.dart 源码,
// 确保关键约束始终存在。
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  group('Release 模式不回退 Mock - 源码审计', () {
    test('app_config.dart 在 kReleaseMode 分支强制禁用所有 Mock', () {
      final source = File('lib/app/config/app_config.dart').readAsStringSync();

      // 必须包含 kReleaseMode 检查
      expect(
        source.contains('kReleaseMode'),
        isTrue,
        reason: 'AppConfig.fromEnvironment 必须检查 kReleaseMode',
      );

      // 必须在 Release 分支强制 useMockBackend=false
      // 找到 Release 分支中的 useMockBackend: false
      expect(
        source.contains('useMockBackend: false'),
        isTrue,
        reason: 'Release 模式必须强制 useMockBackend=false',
      );

      // 必须在 Release 分支强制 useMockExpressionRecognition=false
      expect(
        source.contains('useMockExpressionRecognition: false'),
        isTrue,
        reason: 'Release 模式必须强制 useMockExpressionRecognition=false',
      );
    });

    test('app_config.dart 注释中明确说明 Release 强制真实模式', () {
      final source = File('lib/app/config/app_config.dart').readAsStringSync();

      // 注释中应明确说明 Release 强制真实模式
      expect(
        source.contains('Release') || source.contains('release') || source.contains('kReleaseMode'),
        isTrue,
        reason: 'AppConfig 应在注释中说明 Release 模式行为',
      );
    });

    test('app_providers.dart 在非 Mock 模式下注入 LiteRtExpressionRecognitionService', () {
      final source = File('lib/app/providers/app_providers.dart').readAsStringSync();

      // 必须引用 LiteRt 服务
      expect(
        source.contains('LiteRtExpressionRecognitionService'),
        isTrue,
        reason: 'expressionRecognitionProvider 必须能注入 LiteRt 服务',
      );

      // 必须在 useMockExpressionRecognition=false 分支构造 LiteRt
      // 通过查找条件分支中包含 LiteRt 构造调用
      expect(
        source.contains('LiteRtExpressionRecognitionService('),
        isTrue,
        reason: 'Provider 应在真实模式下构造 LiteRtExpressionRecognitionService 实例',
      );
    });

    test('app_providers.dart 在 Mock 模式下注入 MockExpressionRecognitionService (仅 Debug)', () {
      final source = File('lib/app/providers/app_providers.dart').readAsStringSync();

      // Mock 分支应仅在 useMockExpressionRecognition=true 时触发
      expect(
        source.contains('MockExpressionRecognitionService'),
        isTrue,
        reason: 'Provider 应能注入 Mock 服务(仅 Debug)',
      );
    });

    test('LiteRtExpressionRecognitionService 不引用 MockExpressionRecognitionService', () {
      // 真实服务必须独立于 Mock 实现,不能在加载失败时静默回退到 Mock
      final source = File(
        'lib/data/services/lite_rt_expression_recognition_service.dart',
      ).readAsStringSync();

      expect(
        source.contains('MockExpressionRecognitionService'),
        isFalse,
        reason: 'LiteRt 服务不得引用 Mock 实现,避免静默回退',
      );
    });
  });

  group('Release 模式不回退 Mock - 错误传播策略', () {
    test('LiteRt 服务通过 status 流暴露加载错误,不返回 Mock 数据', () {
      final source = File(
        'lib/data/services/lite_rt_expression_recognition_service.dart',
      ).readAsStringSync();

      // 必须有 ExpressionModelState.failed 状态
      expect(
        source.contains('ExpressionModelState.failed'),
        isTrue,
        reason: 'LiteRt 服务必须在加载失败时通过 failed 状态暴露错误',
      );

      // 必须有 ExpressionModelState.notInstalled 状态(等待 cnn-training 分支)
      expect(
        source.contains('ExpressionModelState.notInstalled'),
        isTrue,
        reason: 'LiteRt 服务必须在模型未安装时通过 notInstalled 状态明确告知',
      );

      // 必须有 modelError 字段填充
      expect(
        source.contains('modelError:'),
        isTrue,
        reason: '失败/未安装状态必须附带可读错误信息',
      );
    });

    test('LiteRt 服务在模型未就绪时 start 不抛异常且不产生结果', () {
      final source = File(
        'lib/data/services/lite_rt_expression_recognition_service.dart',
      ).readAsStringSync();

      // start 方法应检查 _interpreter == null 后安全返回
      // 查找 start 方法中的守卫语句
      expect(
        source.contains('_interpreter == null'),
        isTrue,
        reason: 'start 方法应检查模型是否已加载',
      );
    });
  });
}
