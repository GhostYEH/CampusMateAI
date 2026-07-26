import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:campus_companion/data/services/api/api_client.dart';
import 'package:campus_companion/data/services/api/api_knowledge_base_service.dart';

import '../../../helpers/mock_dio_adapter.dart';

void main() {
  late MockDioAdapter adapter;
  late ApiClient client;
  late ApiKnowledgeBaseService service;

  setUp(() {
    adapter = MockDioAdapter();
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    dio.interceptors.add(adapter);
    client = ApiClient(baseUrl: 'http://test.local', dio: dio);
    service = ApiKnowledgeBaseService(client);
  });

  group('ApiKnowledgeBaseService.sources', () {
    test('正确解析已导入文档列表', () async {
      adapter.registerGet(
        '/api/v1/knowledge/documents',
        data: [
          {
            'document_id': 'doc_1',
            'title': '社会实践申请指南',
            'source_department': '校团委',
            'source_type': 'md',
            'original_filename': '01_social_practice_guide.md',
            'content_hash': 'abc123',
            'published_at': '2026-07-01T00:00:00+08:00',
            'updated_at': '2026-07-10T00:00:00+08:00',
            'effective_from': null,
            'effective_to': null,
            'version': 'v1.2',
            'applicable_students': '2024级本科生',
            'is_official': true,
            'is_expired': false,
            'file_size': 4096,
            'file_ext': 'md',
            'imported_at': '2026-07-15T10:00:00+08:00',
          },
          {
            'document_id': 'doc_2',
            'title': '旧版综合测评办法',
            'source_department': '学工处',
            'source_type': 'txt',
            'original_filename': 'old_eval.txt',
            'content_hash': 'def456',
            'published_at': '2020-01-01T00:00:00+08:00',
            'updated_at': '2020-01-01T00:00:00+08:00',
            'effective_from': null,
            'effective_to': '2021-01-01T00:00:00+08:00',
            'version': 'v1.0',
            'applicable_students': '全体本科生',
            'is_official': true,
            'is_expired': true,
            'file_size': 2048,
            'file_ext': 'txt',
            'imported_at': '2020-02-01T00:00:00+08:00',
          },
        ],
      );

      final sources = await service.sources;

      expect(sources.length, 2);
      // 第一个:最新官方资料
      final first = sources[0];
      expect(first.id, 'doc_1');
      expect(first.title, '社会实践申请指南');
      expect(first.sourceDepartment, '校团委');
      expect(first.publishedAt, isNotNull);
      expect(first.publishedAt!.year, 2026);
      expect(first.version, 'v1.2');
      expect(first.applicableStudents, '2024级本科生');
      expect(first.isOfficial, isTrue);
      expect(first.isExpired, isFalse);
      expect(first.updatedAt.year, 2026);

      // 第二个:过期资料
      final second = sources[1];
      expect(second.id, 'doc_2');
      expect(second.isExpired, isTrue);
      expect(second.isOfficial, isTrue);
      expect(second.version, 'v1.0');
    });

    test('空文档列表返回空 List', () async {
      adapter.registerGet('/api/v1/knowledge/documents', data: []);

      final sources = await service.sources;
      expect(sources, isEmpty);
    });

    test('文档缺少 source_department 时使用默认值', () async {
      adapter.registerGet(
        '/api/v1/knowledge/documents',
        data: [
          {
            'document_id': 'doc_x',
            'title': '未知来源文档',
            'source_department': null,
            'source_type': 'md',
            'original_filename': 'unknown.md',
            'content_hash': 'xyz',
            'published_at': null,
            'updated_at': null,
            'effective_from': null,
            'effective_to': null,
            'version': null,
            'applicable_students': null,
            'is_official': false,
            'is_expired': false,
            'file_size': 100,
            'file_ext': 'md',
            'imported_at': '2026-07-15T10:00:00+08:00',
          },
        ],
      );

      final sources = await service.sources;
      expect(sources.length, 1);
      final s = sources.first;
      expect(s.sourceDepartment, isNull);
      expect(s.source, '演示资料');
      expect(s.version, isNull);
      expect(s.applicableStudents, isNull);
      expect(s.publishedAt, isNull);
      expect(s.updatedAt, isNotNull); // 默认为 now
    });

    test('updated_at 字段非法时使用 now()', () async {
      adapter.registerGet(
        '/api/v1/knowledge/documents',
        data: [
          {
            'document_id': 'doc_bad',
            'title': '文档',
            'source_department': '教务处',
            'source_type': 'md',
            'original_filename': 'bad.md',
            'content_hash': 'h1',
            'published_at': null,
            'updated_at': 'invalid-date',
            'effective_from': null,
            'effective_to': null,
            'version': null,
            'applicable_students': null,
            'is_official': false,
            'is_expired': false,
            'file_size': 100,
            'file_ext': 'md',
            'imported_at': '2026-07-15T10:00:00+08:00',
          },
        ],
      );

      final sources = await service.sources;
      expect(sources.length, 1);
      // 非法日期被捕获,updatedAt 默认为 now
      expect(sources.first.updatedAt, isNotNull);
    });

    test('网络错误抛出 ApiException', () async {
      adapter.registerGetError(
        '/api/v1/knowledge/documents',
        DioException(
          type: DioExceptionType.connectionError,
          message: 'Failed to connect',
          requestOptions: RequestOptions(path: '/api/v1/knowledge/documents'),
        ),
      );

      expect(
        () => service.sources,
        throwsA(
          isA<ApiException>().having((e) => e.code, 'code', 'NETWORK_ERROR'),
        ),
      );
    });

    test('后端 500 错误携带结构化 code', () async {
      adapter.registerGet(
        '/api/v1/knowledge/documents',
        statusCode: 500,
        data: {
          'code': 'KNOWLEDGE_BASE_EMPTY',
          'message': '知识库未初始化',
          'details': null,
        },
      );

      expect(
        () => service.sources,
        throwsA(
          isA<ApiException>()
              .having((e) => e.code, 'code', 'KNOWLEDGE_BASE_EMPTY')
              .having((e) => e.httpStatus, 'httpStatus', 500),
        ),
      );
    });
  });

  group('ApiKnowledgeBaseService.search', () {
    test('返回前 limit 条文档', () async {
      adapter.registerGet(
        '/api/v1/knowledge/documents',
        data: [
          for (var i = 1; i <= 5; i++)
            {
              'document_id': 'doc_$i',
              'title': '文档 $i',
              'source_department': '教务处',
              'source_type': 'md',
              'original_filename': 'doc_$i.md',
              'content_hash': 'h$i',
              'published_at': null,
              'updated_at': null,
              'effective_from': null,
              'effective_to': null,
              'version': null,
              'applicable_students': null,
              'is_official': false,
              'is_expired': false,
              'file_size': 100,
              'file_ext': 'md',
              'imported_at': '2026-07-15T10:00:00+08:00',
            },
        ],
      );

      final sources = await service.search('关键词', limit: 3);
      expect(sources.length, 3);
      expect(sources[0].id, 'doc_1');
      expect(sources[2].id, 'doc_3');
    });

    test('limit 默认值为 3', () async {
      adapter.registerGet(
        '/api/v1/knowledge/documents',
        data: [
          for (var i = 1; i <= 5; i++)
            {
              'document_id': 'doc_$i',
              'title': '文档 $i',
              'source_department': null,
              'source_type': 'md',
              'original_filename': 'doc_$i.md',
              'content_hash': 'h$i',
              'published_at': null,
              'updated_at': null,
              'effective_from': null,
              'effective_to': null,
              'version': null,
              'applicable_students': null,
              'is_official': false,
              'is_expired': false,
              'file_size': 100,
              'file_ext': 'md',
              'imported_at': '2026-07-15T10:00:00+08:00',
            },
        ],
      );

      final sources = await service.search('关键词');
      expect(sources.length, 3);
    });

    test('文档数小于 limit 时返回全部', () async {
      adapter.registerGet(
        '/api/v1/knowledge/documents',
        data: [
          {
            'document_id': 'doc_only',
            'title': '唯一文档',
            'source_department': null,
            'source_type': 'md',
            'original_filename': 'doc.md',
            'content_hash': 'h1',
            'published_at': null,
            'updated_at': null,
            'effective_from': null,
            'effective_to': null,
            'version': null,
            'applicable_students': null,
            'is_official': false,
            'is_expired': false,
            'file_size': 100,
            'file_ext': 'md',
            'imported_at': '2026-07-15T10:00:00+08:00',
          },
        ],
      );

      final sources = await service.search('关键词', limit: 10);
      expect(sources.length, 1);
      expect(sources.first.title, '唯一文档');
    });

    test('网络错误抛出 ApiException', () async {
      adapter.registerGetError(
        '/api/v1/knowledge/documents',
        DioException(
          type: DioExceptionType.connectionTimeout,
          message: 'Timeout',
          requestOptions: RequestOptions(path: '/api/v1/knowledge/documents'),
        ),
      );

      expect(
        () => service.search('关键词'),
        throwsA(isA<ApiException>().having((e) => e.code, 'code', 'TIMEOUT')),
      );
    });
  });
}
