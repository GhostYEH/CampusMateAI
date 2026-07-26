import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/core/widgets/state_views.dart';
import 'package:campus_companion/data/services/api/api_client.dart';
import 'package:campus_companion/features/notifications/presentation/notification_extract_page.dart';

import '../../helpers/mock_dio_adapter.dart';

void main() {
  /// 构造一个可在 Real Backend 模式下注入 Mock Dio 的 ProviderContainer。
  ProviderContainer makeRealBackendContainer(MockDioAdapter adapter) {
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    dio.interceptors.add(adapter);
    return ProviderContainer(
      overrides: [
        appConfigProvider.overrideWith((ref) {
          return const AppConfig(
            environment: AppEnvironment.development,
            useMockBackend: false,
            useMockExpressionRecognition: true,
            apiBaseUrl: 'http://test.local',
          );
        }),
        apiClientProvider.overrideWith((ref) {
          return ApiClient(baseUrl: 'http://test.local', dio: dio);
        }),
        reduceMotionProvider.overrideWith((ref) => true),
      ],
    );
  }

  GoRouter buildRouter() {
    return GoRouter(
      initialLocation: '/notifications/extract',
      routes: [
        GoRoute(
          path: '/home',
          builder: (context, state) => const Scaffold(body: Text('home')),
        ),
        GoRoute(
          path: '/notifications/extract',
          builder: (context, state) => const NotificationExtractPage(),
        ),
      ],
    );
  }

  Widget wrapApp(ProviderContainer container) {
    return UncontrolledProviderScope(
      container: container,
      child: MaterialApp.router(
        theme: ThemeData.light(useMaterial3: true),
        routerConfig: buildRouter(),
      ),
    );
  }

  void setPhoneViewport(WidgetTester tester) {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
  }

  Finder findMainInput() => find.byType(TextFormField).first;
  Finder findExtractButton() => find.byType(FilledButton);

  group('通知整理页 - Real Backend 错误状态与降级', () {
    testWidgets('Real 模式渲染"真实后端"标识', (tester) async {
      setPhoneViewport(tester);
      final adapter = MockDioAdapter();
      final container = makeRealBackendContainer(adapter);
      addTearDown(container.dispose);

      await tester.pumpWidget(wrapApp(container));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // MockNoteBanner 应显示真实后端标识
      expect(find.textContaining('由后端智能抽取'), findsOneWidget);
    });

    testWidgets('网络错误时显示"无法连接后端服务"横幅', (tester) async {
      setPhoneViewport(tester);
      final adapter = MockDioAdapter();
      // 注册一个会抛 connectionError 的路由
      adapter.registerPostError(
        '/api/v1/notices/extract-multi',
        DioException(
          type: DioExceptionType.connectionError,
          message: 'Failed to connect',
          requestOptions: RequestOptions(path: '/api/v1/notices/extract-multi'),
        ),
      );
      final container = makeRealBackendContainer(adapter);
      addTearDown(container.dispose);

      await tester.pumpWidget(wrapApp(container));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // 输入通知文本
      await tester.enterText(
        findMainInput(),
        '请2024级学生于7月30日前填写实践申请表',
      );
      await tester.pump();

      // 点击智能整理按钮
      await tester.tap(findExtractButton());
      await tester.pump();
      // 等待异步错误返回
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      // 应显示错误横幅
      expect(find.text('无法连接后端服务'), findsOneWidget);
      expect(find.text('重试'), findsOneWidget);
      // 参赛版本约束:正式产品不得提供"切换到演示模式"入口
      expect(find.text('切换到演示模式'), findsNothing);
      // 也不应有任何 Mock 降级入口
      expect(find.byIcon(Icons.science_outlined), findsNothing);

      // 关键: 用户输入的通知文本被保留(不清空)
      expect(find.textContaining('请2024级学生'), findsWidgets);
    });

    testWidgets('点击"重试"重新触发后端提取', (tester) async {
      setPhoneViewport(tester);
      final adapter = MockDioAdapter();
      adapter.registerPostError(
        '/api/v1/notices/extract-multi',
        DioException(
          type: DioExceptionType.connectionError,
          message: 'Failed',
          requestOptions: RequestOptions(path: '/api/v1/notices/extract-multi'),
        ),
      );
      final container = makeRealBackendContainer(adapter);
      addTearDown(container.dispose);

      await tester.pumpWidget(wrapApp(container));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // 输入文本
      await tester.enterText(findMainInput(), '请2024级学生填写实践申请表');
      await tester.pump();

      // 第一次提取 → 失败
      await tester.tap(findExtractButton());
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('无法连接后端服务'), findsOneWidget);

      // 重新注册一个成功响应,模拟后端恢复(多任务格式)
      adapter.registerPost(
        '/api/v1/notices/extract-multi',
        data: {
          'tasks': [
            {
              'title': '提交实践申请',
              'task': '提交实践申请',
              'target_students': '2024级',
              'deadline': '2026-07-30T23:59:00+08:00',
              'materials': [
                {'id': 'm_1', 'name': '申请表', 'required': true},
              ],
              'submission_method': null,
              'location': null,
              'source_name': null,
              'source_text': '请2024级学生填写实践申请表',
              'importance': 'important',
              'confidence': 0.7,
              'needs_confirmation': true,
              'warnings': ['提交方式不够明确,建议人工确认'],
              'extracted_at': '2026-07-25T10:00:00+08:00',
              'extractor_mode': 'rules',
            }
          ],
          'split_reason': '单任务',
          'needs_user_confirmation': false,
        },
      );

      // 点击重试
      await tester.tap(find.text('重试'));
      await tester.pump();
      // 等待重新提取完成(ApiNotificationExtractionService 有 5 个 80ms 步骤 = 400ms+)
      // 多 pump 几次让异步链全部消化,避免 timer pending。
      for (var i = 0; i < 6; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }

      // 错误横幅消失
      expect(find.text('无法连接后端服务'), findsNothing);

      // 结果表单出现
      expect(find.text('任务信息'), findsOneWidget);
    });

    testWidgets('后端 500 错误时也展示错误横幅', (tester) async {
      setPhoneViewport(tester);
      final adapter = MockDioAdapter();
      adapter.registerPost(
        '/api/v1/notices/extract-multi',
        statusCode: 500,
        data: {
          'code': 'NOTICE_UNPARSEABLE',
          'message': '文本不像校园通知',
          'details': null,
        },
      );
      final container = makeRealBackendContainer(adapter);
      addTearDown(container.dispose);

      await tester.pumpWidget(wrapApp(container));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.enterText(findMainInput(), '某条短文本');
      await tester.pump();

      await tester.tap(findExtractButton());
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('无法连接后端服务'), findsOneWidget);
      expect(find.textContaining('文本不像校园通知'), findsOneWidget);
    });

    testWidgets('成功提取后展示 warnings 横幅(rules 模式)', (tester) async {
      setPhoneViewport(tester);
      final adapter = MockDioAdapter();
      adapter.registerPost(
        '/api/v1/notices/extract-multi',
        data: {
          'tasks': [
            {
              'title': '完成活动报名',
              'task': '完成活动报名',
              'target_students': null,
              'deadline': null,
              'materials': [],
              'submission_method': null,
              'location': null,
              'source_name': null,
              'source_text': '完成活动报名',
              'importance': 'normal',
              'confidence': 0.3,
              'needs_confirmation': true,
              'warnings': [
                '通知未明确面向对象,建议人工确认',
                '未识别到明确截止时间,建议人工确认',
              ],
              'extracted_at': '2026-07-25T10:00:00+08:00',
              'extractor_mode': 'rules',
            }
          ],
          'split_reason': '单任务',
          'needs_user_confirmation': false,
        },
      );
      final container = makeRealBackendContainer(adapter);
      addTearDown(container.dispose);

      await tester.pumpWidget(wrapApp(container));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.enterText(findMainInput(), '完成活动报名');
      await tester.pump();

      await tester.tap(findExtractButton());
      await tester.pump();
      // 等待 extract 完成:5 个 80ms 步骤 + 渲染 buffer
      for (var i = 0; i < 6; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }

      // 出现"需要确认"横幅(温和提示,非错误)
      expect(find.text('需要确认'), findsOneWidget);
      expect(find.text('本地规则提取'), findsOneWidget);
      // warnings 内容显示(精确匹配 warning 文本,避免与表单 label 冲突)
      expect(find.text('通知未明确面向对象,建议人工确认'), findsOneWidget);
      expect(find.text('未识别到明确截止时间,建议人工确认'), findsOneWidget);
      // 置信度展示
      expect(find.textContaining('提取置信度'), findsOneWidget);
    });
  });
}
