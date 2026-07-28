import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:campus_companion/data/models/expression.dart';
import 'package:campus_companion/data/services/expression_service_status.dart';
import 'package:campus_companion/data/services/service_interfaces.dart' show PermissionStatus;
import 'package:campus_companion/features/study_companion/presentation/widgets/expression_panel.dart';

void main() {
  ExpressionResult makeResult({
    ExpressionLabel label = ExpressionLabel.happy,
    double confidence = 0.85,
    bool isStable = true,
  }) {
    return ExpressionResult(
      label: label,
      confidence: confidence,
      probabilities: {
        for (final l in ExpressionLabel.values)
          l: l == label ? confidence : (1 - confidence) / 8,
      },
      timestamp: DateTime.now(),
      isStable: isStable,
      modelVersion: 'test-v1.0',
    );
  }

  group('ExpressionPanel - 权限拒绝状态显示', () {
    testWidgets('permanentlyDenied 时显示"前往系统设置"提示,不显示开启按钮', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ExpressionPanel(
              enabled: false,
              result: null,
              recentStable: const [],
              onInject: (_) {},
              showMockConsole: false,
              isMockMode: false,
              userEnabled: false,
              isRequestingPermission: false,
              cameraPermissionStatus: PermissionStatus.permanentlyDenied,
              onToggle: () {},
            ),
          ),
        ),
      );

      // 应显示"被永久拒绝"提示
      expect(find.textContaining('摄像头权限被永久拒绝'), findsOneWidget);
      // 不应显示"开启识别"按钮(因为权限已被永久拒绝)
      expect(find.text('开启识别'), findsNothing);
    });

    testWidgets('granted + userEnabled=false 时显示"开启识别"按钮', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ExpressionPanel(
              enabled: false,
              result: null,
              recentStable: const [],
              onInject: (_) {},
              showMockConsole: false,
              isMockMode: false,
              userEnabled: false,
              isRequestingPermission: false,
              cameraPermissionStatus: PermissionStatus.granted,
              onToggle: () {},
            ),
          ),
        ),
      );

      expect(find.text('开启识别'), findsOneWidget);
      expect(find.textContaining('主动开启后才会启动摄像头'), findsOneWidget);
    });

    testWidgets('userEnabled=true 时显示"关闭识别"按钮', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ExpressionPanel(
              enabled: true,
              result: makeResult(),
              recentStable: const [],
              onInject: (_) {},
              showMockConsole: false,
              isMockMode: false,
              userEnabled: true,
              isRequestingPermission: false,
              cameraPermissionStatus: PermissionStatus.granted,
              onToggle: () {},
              status: const ExpressionServiceStatus(
                modelState: ExpressionModelState.ready,
                cameraState: CameraState.running,
                modelVersion: 'test-v1.0',
              ),
            ),
          ),
        ),
      );

      expect(find.text('关闭识别'), findsOneWidget);
      expect(find.textContaining('已开启摄像头识别'), findsOneWidget);
    });

    testWidgets('isRequestingPermission=true 时按钮被禁用且显示加载指示', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ExpressionPanel(
              enabled: false,
              result: null,
              recentStable: const [],
              onInject: (_) {},
              showMockConsole: false,
              isMockMode: false,
              userEnabled: false,
              isRequestingPermission: true,
              cameraPermissionStatus: PermissionStatus.notDetermined,
              onToggle: () {},
            ),
          ),
        ),
      );

      // 按钮显示"请求权限中…",onPressed 为 null(禁用)
      final button = find.byType(FilledButton).first;
      final widget = tester.widget<FilledButton>(button);
      expect(widget.onPressed, isNull);
      expect(find.text('请求权限中…'), findsOneWidget);
    });

    testWidgets('点击"开启识别"触发 onToggle 回调', (tester) async {
      var toggleCalled = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ExpressionPanel(
              enabled: false,
              result: null,
              recentStable: const [],
              onInject: (_) {},
              showMockConsole: false,
              isMockMode: false,
              userEnabled: false,
              isRequestingPermission: false,
              cameraPermissionStatus: PermissionStatus.granted,
              onToggle: () => toggleCalled = true,
            ),
          ),
        ),
      );

      await tester.tap(find.text('开启识别'));
      await tester.pump();

      expect(toggleCalled, isTrue);
    });
  });

  group('ExpressionPanel - 模型状态显示', () {
    testWidgets('未安装模型时显示明确提示,不假装可用', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: ExpressionPanel(
                enabled: true,
                result: null,
                recentStable: const [],
                onInject: (_) {},
                showMockConsole: false,
                isMockMode: false,
                userEnabled: true,
                isRequestingPermission: false,
                cameraPermissionStatus: PermissionStatus.granted,
                onToggle: () {},
                status: const ExpressionServiceStatus(
                  modelState: ExpressionModelState.notInstalled,
                  cameraState: CameraState.idle,
                  modelVersion: '',
                  modelError: '请等待 cnn-training 分支提供 expression_model.tflite',
                ),
              ),
            ),
          ),
        ),
      );

      expect(find.text('模型未安装'), findsOneWidget);
      expect(find.textContaining('cnn-training'), findsOneWidget);
    });

    testWidgets('平台降级 (Web) 时显示明确降级提示', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: ExpressionPanel(
                enabled: false,
                result: null,
                recentStable: const [],
                onInject: (_) {},
                showMockConsole: false,
                isMockMode: false,
                userEnabled: false,
                isRequestingPermission: false,
                cameraPermissionStatus: PermissionStatus.granted,
                onToggle: () {},
                status: const ExpressionServiceStatus(
                  modelState: ExpressionModelState.idle,
                  cameraState: CameraState.idle,
                  modelVersion: '',
                  platformDegradation:
                      'Web 平台不支持 TFLite CNN 推理与 ML Kit 人脸检测,'
                      '表情识别功能不可用。请在 Android 或 iOS 设备上使用。',
                ),
              ),
            ),
          ),
        ),
      );

      // 应显示降级提示(明确告知用户平台不支持,不静默回退 Mock)
      expect(find.textContaining('Web 平台不支持'), findsOneWidget);
      // 切换按钮仍在(用户可尝试开启,但点击后服务会保持降级状态)
      expect(find.text('开启识别'), findsOneWidget);
    });

    testWidgets('Mock 模式显示明显 Mock 标识', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ExpressionPanel(
              enabled: true,
              result: makeResult(),
              recentStable: const [],
              onInject: (_) {},
              showMockConsole: false,
              isMockMode: true, // Mock 模式
              userEnabled: true,
              isRequestingPermission: false,
              cameraPermissionStatus: PermissionStatus.granted,
              onToggle: () {},
              status: const ExpressionServiceStatus(
                modelState: ExpressionModelState.ready,
                cameraState: CameraState.running,
                modelVersion: 'mock-v0.1',
              ),
            ),
          ),
        ),
      );

      // 应显示 Mock 模式标识
      expect(find.textContaining('Mock 模式'), findsOneWidget);
    });
  });

  group('ExpressionPanel - 科学边界文案', () {
    testWidgets('UI 显示"仅识别可观察表情,不作心理诊断"提示', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ExpressionPanel(
              enabled: true,
              result: makeResult(),
              recentStable: const [],
              onInject: (_) {},
              showMockConsole: false,
              isMockMode: false,
              userEnabled: true,
              isRequestingPermission: false,
              cameraPermissionStatus: PermissionStatus.granted,
              onToggle: () {},
              status: const ExpressionServiceStatus(
                modelState: ExpressionModelState.ready,
                cameraState: CameraState.running,
                modelVersion: 'test-v1.0',
              ),
            ),
          ),
        ),
      );

      // 应显示科学边界提示
      expect(find.textContaining('仅识别可观察表情'), findsOneWidget);
      expect(find.textContaining('不作心理诊断'), findsOneWidget);
    });

    testWidgets('UI 不出现"焦虑""抑郁"等诊断式文案', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ExpressionPanel(
              enabled: true,
              result: makeResult(),
              recentStable: const [],
              onInject: (_) {},
              showMockConsole: false,
              isMockMode: false,
              userEnabled: true,
              isRequestingPermission: false,
              cameraPermissionStatus: PermissionStatus.granted,
              onToggle: () {},
              status: const ExpressionServiceStatus(
                modelState: ExpressionModelState.ready,
                cameraState: CameraState.running,
                modelVersion: 'test-v1.0',
              ),
            ),
          ),
        ),
      );

      final allText = tester.widgetList<Text>(find.byType(Text)).map((t) => t.data ?? '').join(' ');
      // 禁止出现诊断式文案
      expect(allText, isNot(contains('你很焦虑')));
      expect(allText, isNot(contains('你抑郁了')));
      expect(allText, isNot(contains('检测出你患有')));
      expect(allText, isNot(contains('已确认你的心理状态')));
    });
  });
}
