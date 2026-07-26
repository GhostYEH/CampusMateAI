import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:campus_companion/data/models/notice.dart';
import 'package:campus_companion/data/services/api/api_client.dart';
import 'package:campus_companion/data/services/api/api_notification_extraction_service.dart';
import 'package:campus_companion/data/services/service_interfaces.dart';

import '../../../helpers/mock_dio_adapter.dart';

void main() {
  late MockDioAdapter adapter;
  late ApiClient client;
  late ApiNotificationExtractionService service;

  setUp(() {
    adapter = MockDioAdapter();
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    dio.interceptors.add(adapter);
    client = ApiClient(baseUrl: 'http://test.local', dio: dio);
    service = ApiNotificationExtractionService(client);
  });

  group('ApiNotificationExtractionService.extract', () {
    test('正常返回结构化抽取结果(LLM 模式)', () async {
      adapter.registerPost(
        '/api/v1/notices/extract',
        data: {
          'title': '提交实践申请',
          'task': '提交实践申请',
          'target_students': '2024级',
          'deadline': '2026-07-30T23:59:00+08:00',
          'materials': [
            {'id': 'm_1', 'name': '申请表', 'required': true},
            {'id': 'm_2', 'name': '证明材料', 'required': true},
          ],
          'submission_method': '提交纸质版',
          'location': '学院办公室',
          'source_name': '信息工程学院通知',
          'source_text': '原文',
          'importance': 'important',
          'confidence': 0.85,
          'needs_confirmation': false,
          'warnings': [],
          'extracted_at': '2026-07-25T10:00:00+08:00',
          'extractor_mode': 'llm',
        },
      );

      final result = await service.extract('请2024级学生于7月30日前填写实践申请表');

      expect(result.taskName, '提交实践申请');
      expect(result.targetAudience, '2024级');
      expect(result.deadline, isNotNull);
      expect(result.deadline!.year, 2026);
      expect(result.deadline!.month, 7);
      expect(result.deadline!.day, 30);
      expect(result.materials.length, 2);
      expect(result.materials[0].name, '申请表');
      expect(result.materials[0].required, isTrue);
      expect(result.submitMethod, '提交纸质版');
      expect(result.location, '学院办公室');
      expect(result.sourceText, '请2024级学生于7月30日前填写实践申请表');
      expect(result.importance, NoticeImportance.important);
      expect(result.confidence, 0.85);
      expect(result.warnings, isEmpty);
      expect(result.extractorMode, 'llm');
      expect(result.needsConfirmation, isFalse);
    });

    test('规则模式返回 warnings 并设置 extractorMode=rules', () async {
      adapter.registerPost(
        '/api/v1/notices/extract',
        data: {
          'title': '完成活动报名',
          'task': '完成活动报名',
          'target_students': null,
          'deadline': null,
          'materials': [],
          'submission_method': null,
          'location': null,
          'source_name': null,
          'source_text': '某通知',
          'importance': 'normal',
          'confidence': 0.3,
          'needs_confirmation': true,
          'warnings': [
            '通知未明确面向对象,建议人工确认',
            '未识别到明确截止时间,建议人工确认',
          ],
          'extracted_at': '2026-07-25T10:00:00+08:00',
          'extractor_mode': 'rules',
        },
      );

      final result = await service.extract('某通知');

      expect(result.taskName, '完成活动报名');
      expect(result.targetAudience, isNull);
      expect(result.deadline, isNull);
      expect(result.materials, isEmpty);
      expect(result.confidence, 0.3);
      expect(result.warnings.length, 2);
      expect(result.warnings.first, contains('面向对象'));
      expect(result.extractorMode, 'rules');
      expect(result.needsConfirmation, isTrue);
    });

    test('进度回调按顺序触发 6 次(0~5)', () async {
      adapter.registerPost(
        '/api/v1/notices/extract',
        data: {
          'title': 't',
          'task': 't',
          'materials': [],
          'source_text': '',
          'importance': 'unknown',
          'confidence': 0.0,
          'needs_confirmation': false,
          'warnings': [],
          'extracted_at': '2026-07-25T10:00:00+08:00',
          'extractor_mode': 'rules',
        },
      );

      final steps = <ExtractionStep>[];
      await service.extract('某通知', onProgress: (s) => steps.add(s));

      // 步骤 0 + 步骤 1~5 = 6 次
      expect(steps.length, 6);
      expect(steps.first.order, 0);
      expect(steps.first.label, '正在连接后端服务');
      expect(steps.last.order, 5);
      expect(steps.last.label, '判断提交方式与地点');
    });

    test('网络错误抛出 ApiException (NETWORK_ERROR)', () async {
      adapter.registerPostError(
        '/api/v1/notices/extract',
        DioException(
          type: DioExceptionType.connectionError,
          message: 'Failed to connect',
          requestOptions: RequestOptions(path: '/api/v1/notices/extract'),
        ),
      );

      expect(
        () => service.extract('某通知'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            'NETWORK_ERROR',
          ),
        ),
      );
    });

    test('超时错误抛出 ApiException (TIMEOUT)', () async {
      adapter.registerPostError(
        '/api/v1/notices/extract',
        DioException(
          type: DioExceptionType.receiveTimeout,
          message: 'Receive timeout',
          requestOptions: RequestOptions(path: '/api/v1/notices/extract'),
        ),
      );

      expect(
        () => service.extract('某通知'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            'TIMEOUT',
          ),
        ),
      );
    });

    test('后端 500 错误携带结构化 code 与 message', () async {
      adapter.registerPost(
        '/api/v1/notices/extract',
        statusCode: 500,
        data: {
          'code': 'NOTICE_UNPARSEABLE',
          'message': '文本不像校园通知',
          'details': null,
        },
      );

      expect(
        () => service.extract('hello world'),
        throwsA(
          isA<ApiException>()
              .having((e) => e.code, 'code', 'NOTICE_UNPARSEABLE')
              .having((e) => e.message, 'message', '文本不像校园通知')
              .having((e) => e.httpStatus, 'httpStatus', 500),
        ),
      );
    });

    test('deadline 解析失败时设置为 null', () async {
      adapter.registerPost(
        '/api/v1/notices/extract',
        data: {
          'title': 't',
          'task': 't',
          'deadline': 'not-a-valid-date',
          'materials': [],
          'source_text': '',
          'importance': 'unknown',
          'confidence': 0.0,
          'needs_confirmation': false,
          'warnings': [],
          'extracted_at': '2026-07-25T10:00:00+08:00',
          'extractor_mode': 'rules',
        },
      );

      final result = await service.extract('某通知');
      expect(result.deadline, isNull);
    });

    test('空 materials 列表正确解析', () async {
      adapter.registerPost(
        '/api/v1/notices/extract',
        data: {
          'title': 't',
          'task': 't',
          'materials': [],
          'source_text': '',
          'importance': 'unknown',
          'confidence': 0.0,
          'needs_confirmation': false,
          'warnings': [],
          'extracted_at': '2026-07-25T10:00:00+08:00',
          'extractor_mode': 'rules',
        },
      );

      final result = await service.extract('某通知');
      expect(result.materials, isEmpty);
    });

    test('materials 含 null name 时被跳过', () async {
      adapter.registerPost(
        '/api/v1/notices/extract',
        data: {
          'title': 't',
          'task': 't',
          'materials': [
            {'id': 'm_1', 'name': '申请表', 'required': true},
            {'id': 'm_2', 'name': '', 'required': true},
            {'id': 'm_3', 'required': true},
          ],
          'source_text': '',
          'importance': 'unknown',
          'confidence': 0.0,
          'needs_confirmation': false,
          'warnings': [],
          'extracted_at': '2026-07-25T10:00:00+08:00',
          'extractor_mode': 'rules',
        },
      );

      final result = await service.extract('某通知');
      expect(result.materials.length, 1);
      expect(result.materials.first.name, '申请表');
    });

    test('请求 body 包含 content 字段', () async {
      adapter.registerPost(
        '/api/v1/notices/extract',
        data: {
          'title': 't',
          'task': 't',
          'materials': [],
          'source_text': '',
          'importance': 'unknown',
          'confidence': 0.0,
          'needs_confirmation': false,
          'warnings': [],
          'extracted_at': '2026-07-25T10:00:00+08:00',
          'extractor_mode': 'rules',
        },
      );

      await service.extract('请2024级学生填写实践申请表');

      expect(adapter.recordedRequests, isNotEmpty);
      final req = adapter.recordedRequests.last;
      expect(req.method, 'POST');
      expect(req.path, '/api/v1/notices/extract');
      expect((req.data as Map<String, dynamic>)['content'], '请2024级学生填写实践申请表');
    });

    test('importance 字段无法识别时安全 fallback 为 unknown', () async {
      adapter.registerPost(
        '/api/v1/notices/extract',
        data: {
          'title': 't',
          'task': 't',
          'materials': [],
          'source_text': '',
          'importance': '未知级别',
          'confidence': 0.0,
          'needs_confirmation': false,
          'warnings': [],
          'extracted_at': '2026-07-25T10:00:00+08:00',
          'extractor_mode': 'rules',
        },
      );

      final result = await service.extract('某通知');
      expect(result.importance, NoticeImportance.unknown);
    });

    test('warnings 列表正确解析为 List<String>', () async {
      adapter.registerPost(
        '/api/v1/notices/extract',
        data: {
          'title': 't',
          'task': 't',
          'materials': [],
          'source_text': '',
          'importance': 'unknown',
          'confidence': 0.4,
          'needs_confirmation': true,
          'warnings': ['通知未标注年份', '面向对象不明'],
          'extracted_at': '2026-07-25T10:00:00+08:00',
          'extractor_mode': 'rules',
        },
      );

      final result = await service.extract('某通知');
      expect(result.warnings.length, 2);
      expect(result.warnings[0], '通知未标注年份');
      expect(result.warnings[1], '面向对象不明');
    });

    test('target_students 为空字符串时解析为 null', () async {
      adapter.registerPost(
        '/api/v1/notices/extract',
        data: {
          'title': 't',
          'task': 't',
          'target_students': '',
          'materials': [],
          'source_text': '',
          'importance': 'unknown',
          'confidence': 0.0,
          'needs_confirmation': false,
          'warnings': [],
          'extracted_at': '2026-07-25T10:00:00+08:00',
          'extractor_mode': 'rules',
        },
      );

      final result = await service.extract('某通知');
      expect(result.targetAudience, isNull);
    });
  });
}
