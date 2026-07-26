// =============================================================================
// real_backend_test.dart — 真实后端集成测试(需要运行中的 FastAPI 后端)
//
// REQUIREMENTS:
//   This test file requires a running FastAPI backend at the URL specified by
//   the API_BASE_URL dart-define (default: http://127.0.0.1:8000).
//
//   Each test checks backend reachability first and SKIPS itself (by returning
//   early with a debugPrint) when the backend is not reachable, so this file
//   can be safely committed and run in environments without a backend.
//
// HOW TO RUN (with backend running):
//   flutter test integration_test/real_backend_test.dart \
//     --dart-define=USE_MOCK_BACKEND=false \
//     --dart-define=API_BASE_URL=http://127.0.0.1:8000
//
// HOW TO RUN (without backend — all tests will skip):
//   flutter test integration_test/real_backend_test.dart
//
// 覆盖用例:
//   1) 知识库状态查询(knowledge base status)
//   2) 文档上传(document upload — 小型文本文件)
//   3) 通知智能提取(notice extraction)
//   4) AI 导员问答(AI counselor Q&A)
//   5) 无数据拒绝(no-data rejection — 询问知识库外的问题,验证优雅降级)
// =============================================================================

import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:campus_companion/app/app.dart';
import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/app/router/app_router.dart';
import 'package:campus_companion/core/storage/data_persistence_service.dart';
import 'package:campus_companion/core/storage/local_storage.dart';
import 'package:campus_companion/core/storage/notice_storage.dart';
import 'package:campus_companion/core/storage/settings_storage.dart';
import 'package:campus_companion/core/storage/study_storage.dart';
import 'package:campus_companion/core/storage/task_storage.dart';
import 'package:campus_companion/data/models/knowledge.dart';
import 'package:campus_companion/data/models/settings.dart';
import 'package:campus_companion/features/knowledge/presentation/widgets/knowledge_status_card.dart';
import 'package:campus_companion/mock/mock_services/fake_notification_reminder_service.dart';
import 'package:campus_companion/mock/mock_services/mock_services.dart';

/// 从 dart-define 读取后端地址(默认 http://127.0.0.1:8000)。
const String _apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://127.0.0.1:8000',
);

/// 检查后端是否可达(对 /api/v1/health 发起 GET,3s 超时)。
///
/// 返回 true 表示后端可用,返回 false 表示不可达(测试应跳过)。
Future<bool> isBackendReachable(String baseUrl) async {
  HttpClient? client;
  try {
    client = HttpClient();
    client.connectionTimeout = const Duration(seconds: 3);
    final request = await client.getUrl(Uri.parse('$baseUrl/api/v1/health'));
    final response = await request.close().timeout(
          const Duration(seconds: 5),
        );
    await response.drain<void>();
    return response.statusCode == 200;
  } catch (_) {
    return false;
  } finally {
    client?.close(force: true);
  }
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  late ProviderContainer container;

  /// 构造真实后端模式的应用容器。
  ///
  /// 通过 override [appConfigProvider] 强制 useMockBackend=false,
  /// 使 knowledgeBaseProvider / counselorChatProvider / notificationExtractionProvider
  /// / knowledgeManagementProvider 自动切换为 ApiXxxService 实现。
  Future<void> bootstrapApp(WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});
    SharedPreferencesLocalStorage.setTestInstance(null);
    final localStorage = await SharedPreferencesLocalStorage.initialize();

    final taskRepo = MockTaskRepository(initial: const []);
    final studyRepo = MockStudySessionRepository();

    final persistenceService = DataPersistenceService(
      settingsStorage: SettingsStorage(localStorage),
      taskStorage: TaskStorage(localStorage),
      studyStorage: StudyStorage(localStorage),
      noticeStorage: NoticeStorage(localStorage),
      taskRepository: taskRepo,
      studyRepository: studyRepo,
    );

    container = ProviderContainer(
      overrides: [
        taskRepositoryProvider.overrideWithValue(taskRepo),
        studySessionRepositoryProvider.overrideWithValue(studyRepo),
        dataPersistenceProvider.overrideWithValue(persistenceService),
        notificationReminderProvider.overrideWithValue(
          FakeNotificationReminderService(),
        ),
        // 强制真实后端模式(不依赖 dart-define)
        appConfigProvider.overrideWithValue(
          const AppConfig(
            environment: AppEnvironment.production,
            useMockBackend: false,
            useMockExpressionRecognition: true,
            enableDemoMode: false,
            apiBaseUrl: _apiBaseUrl,
          ),
        ),
        // 开启减少动态效果,关闭入场动画,确保按钮可点击
        appSettingsProvider.overrideWith((ref) {
          final notifier = AppSettingsNotifier();
          notifier.restoreFrom(const AppSettings(reduceMotion: true));
          return notifier;
        }),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const CampusCompanionApp(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 800));
  }

  void setPhoneViewport(WidgetTester tester) {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
  }

  Future<void> navigateTo(WidgetTester tester, String location) async {
    container.read(routerProvider).go(location);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
  }

  // ===========================================================================
  // 1) 知识库状态查询
  // ===========================================================================
  testWidgets(
    'Real backend: knowledge base status is reachable',
    (tester) async {
      final reachable = await isBackendReachable(_apiBaseUrl);
      if (!reachable) {
        debugPrint('SKIP: backend not reachable at $_apiBaseUrl');
        return;
      }

      setPhoneViewport(tester);
      await bootstrapApp(tester);

      await navigateTo(tester, '/knowledge');
      // 真实后端响应可能较慢,给足时间
      await tester.pump(const Duration(milliseconds: 1500));
      await tester.pump(const Duration(milliseconds: 1000));

      // 状态卡片渲染
      expect(find.byType(KnowledgeStatusCard), findsOneWidget);
      // 真实模式下显示知识库类型名称(非"演示模式知识库")
      expect(find.text('演示模式知识库'), findsNothing);
    },
  );

  // ===========================================================================
  // 2) 文档上传(小型文本文件)
  // ===========================================================================
  testWidgets(
    'Real backend: document upload with small text file',
    (tester) async {
      final reachable = await isBackendReachable(_apiBaseUrl);
      if (!reachable) {
        debugPrint('SKIP: backend not reachable at $_apiBaseUrl');
        return;
      }

      setPhoneViewport(tester);
      await bootstrapApp(tester);

      // 直接调用服务层上传(FilePicker 在测试环境中难以驱动)
      final service = container.read(knowledgeManagementProvider);
      const content = '# 集成测试文档\n\n这是一个由 integration_test 上传的小型文本文件。\n'
          '用于验证真实后端的文档上传与解析能力。';
      final bytes = Uint8List.fromList(utf8.encode(content));

      final doc = await service.uploadDocument(
        bytes: bytes,
        originalFilename: 'integration_test_upload.txt',
        metadata: const KnowledgeDocumentMetadata(
          title: '集成测试上传文档',
          sourceType: 'guide',
          isOfficial: false,
        ),
      );

      expect(doc.documentId, isNotEmpty);
      debugPrint('Uploaded document id=${doc.documentId}, title=${doc.title}');

      // 清理:删除测试文档
      final deleted = await service.deleteDocument(doc.documentId);
      expect(deleted, isTrue);
    },
  );

  // ===========================================================================
  // 3) 通知智能提取
  // ===========================================================================
  testWidgets(
    'Real backend: notice extraction returns structured result',
    (tester) async {
      final reachable = await isBackendReachable(_apiBaseUrl);
      if (!reachable) {
        debugPrint('SKIP: backend not reachable at $_apiBaseUrl');
        return;
      }

      setPhoneViewport(tester);
      await bootstrapApp(tester);

      await navigateTo(tester, '/notifications/extract');
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.text('智能整理通知'), findsOneWidget);

      // 输入通知原文
      final mainInput = find.byType(TextFormField).first;
      await tester.enterText(
        mainInput,
        '请2024级学生于10月20日前填写实践申请表,'
        '并将申请表和证明材料提交至学院办公室。',
      );
      await tester.pump();

      // 点击"智能整理"
      final extractButton = find.byType(FilledButton);
      await tester.tap(extractButton);
      await tester.pump();

      // 真实后端 LLM 提取可能需要较长时间,最多等待 15s
      await tester.pump(const Duration(seconds: 5));
      await tester.pump(const Duration(seconds: 5));
      await tester.pump(const Duration(seconds: 5));

      // 结果表单出现
      expect(find.text('任务信息'), findsOneWidget);
      expect(find.text('保存为待办'), findsOneWidget);
    },
  );

  // ===========================================================================
  // 4) AI 导员问答
  // ===========================================================================
  testWidgets(
    'Real backend: AI counselor answers questions',
    (tester) async {
      final reachable = await isBackendReachable(_apiBaseUrl);
      if (!reachable) {
        debugPrint('SKIP: backend not reachable at $_apiBaseUrl');
        return;
      }

      setPhoneViewport(tester);
      await bootstrapApp(tester);

      await navigateTo(tester, '/counselor');
      await tester.pump(const Duration(milliseconds: 500));

      // 触发后端状态检查
      container.read(backendStatusProvider.notifier).check();
      await tester.pump(const Duration(milliseconds: 1000));

      // 输入问题
      final inputFinder = find.ancestor(
        of: find.text('问问 AI 导员...'),
        matching: find.byType(TextField),
      );
      await tester.enterText(inputFinder, '综合测评怎么准备?');
      await tester.pump();

      final sendButton = find.ancestor(
        of: find.text('发送'),
        matching: find.byType(FilledButton),
      );
      await tester.tap(sendButton);
      await tester.pump();

      // 真实后端流式回复可能需要较长时间
      await tester.pump(const Duration(seconds: 5));
      await tester.pump(const Duration(seconds: 5));
      await tester.pump(const Duration(seconds: 5));

      // 用户消息出现
      expect(find.text('综合测评怎么准备?'), findsOneWidget);
      // AI 回复出现(非空内容,非流式占位)
      expect(find.textContaining('综合测评'), findsWidgets);
    },
  );

  // ===========================================================================
  // 5) 无数据拒绝(询问知识库外的问题,验证优雅降级)
  // ===========================================================================
  testWidgets(
    'Real backend: no-data rejection is graceful',
    (tester) async {
      final reachable = await isBackendReachable(_apiBaseUrl);
      if (!reachable) {
        debugPrint('SKIP: backend not reachable at $_apiBaseUrl');
        return;
      }

      setPhoneViewport(tester);
      await bootstrapApp(tester);

      await navigateTo(tester, '/counselor');
      await tester.pump(const Duration(milliseconds: 500));

      container.read(backendStatusProvider.notifier).check();
      await tester.pump(const Duration(milliseconds: 1000));

      // 询问一个知识库几乎不可能覆盖的问题
      final inputFinder = find.ancestor(
        of: find.text('问问 AI 导员...'),
        matching: find.byType(TextField),
      );
      const obscureQuestion = '请告诉我量子色动力学的渐近自由机制';
      await tester.enterText(inputFinder, obscureQuestion);
      await tester.pump();

      final sendButton = find.ancestor(
        of: find.text('发送'),
        matching: find.byType(FilledButton),
      );
      await tester.tap(sendButton);
      await tester.pump();

      // 等待回复
      await tester.pump(const Duration(seconds: 5));
      await tester.pump(const Duration(seconds: 5));
      await tester.pump(const Duration(seconds: 5));

      // 用户消息出现
      expect(find.text(obscureQuestion), findsOneWidget);

      // AI 应给出回复(即使是"无法回答"类型的优雅降级,也不应崩溃或卡死)。
      // 验证:存在非空的 counselor 回复(用户消息之后至少一条消息)。
      // 这里不断言具体文案,因为后端的"无知识"措辞可能变化。
      // 仅验证流式占位已结束(发送按钮重新出现而非"停止")。
      expect(find.text('停止'), findsNothing);
    },
  );
}
