// 隐私审计测试 — 验证表情识别链路不保存图片/视频/不上传帧
//
// 实现方式: 通过静态分析源代码,确保关键模块不引入任何文件 I/O 或网络调用。
// 这是一类"源码审计型"测试,在 CI 中可阻止后续修改意外引入隐私违规。
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// 表情识别链路核心源文件路径(必须无文件 I/O 与网络调用)。
const _expressionSourceFiles = <String>[
  // 推理服务
  'lib/data/services/lite_rt_expression_recognition_service.dart',
  // 模型配置加载(仅 rootBundle 读 asset)
  'lib/data/services/expression_model_config.dart',
  // 图像预处理(纯内存)
  'lib/data/services/expression_preprocessor.dart',
  // 摄像头帧转换(纯内存)
  'lib/data/services/camera_frame_converter.dart',
  // 服务状态定义
  'lib/data/services/expression_service_status.dart',
];

/// 禁止在表情识别链路中出现的"写文件"调用模式。
final _forbiddenFileWritePatterns = <RegExp>[
  RegExp(r'\bFile\s*\('), // File(...) 构造
  RegExp(r'\.writeAsBytes\s*\('),
  RegExp(r'\.writeAsString\s*\('),
  RegExp(r'\.writeAsStringSync\s*\('),
  RegExp(r'\.writeToFileSync\s*\('),
  RegExp(r'image_gallery_saver'),
  RegExp(r'\bsaveToGallery\b'),
  RegExp(r'\bsaveImageToFile\b'),
  RegExp(r'\bpath_provider\b.*\bsave\b'),
];

/// 禁止在表情识别链路中出现的"网络上传"调用模式。
final _forbiddenNetworkPatterns = <RegExp>[
  RegExp(r'\bDio\b.*\.(post|put|send|upload)\b'),
  RegExp(r'\bhttp\.MultipartRequest\b'),
  RegExp(r'\buploadImage\b'),
  RegExp(r'\buploadFrame\b'),
  RegExp(r'\bHttpClient\b'),
];

void main() {
  group('表情识别隐私审计 - 不保存图片/视频文件', () {
    for (final path in _expressionSourceFiles) {
      test('$path 不包含任何文件写入 API 调用', () {
        final file = File(path);
        expect(
          file.existsSync(),
          isTrue,
          reason: '$path 不存在,无法审计',
        );
        final source = file.readAsStringSync();

        for (final pattern in _forbiddenFileWritePatterns) {
          expect(
            pattern.hasMatch(source),
            isFalse,
            reason: '$path 命中禁止的文件写入模式: ${pattern.pattern}\n'
                '表情识别链路禁止保存任何图片/视频文件(AGENTS.md §3)',
          );
        }
      });
    }
  });

  group('表情识别隐私审计 - 不上传摄像头帧', () {
    for (final path in _expressionSourceFiles) {
      test('$path 不包含任何网络上传调用', () {
        final file = File(path);
        expect(
          file.existsSync(),
          isTrue,
          reason: '$path 不存在,无法审计',
        );
        final source = file.readAsStringSync();

        for (final pattern in _forbiddenNetworkPatterns) {
          expect(
            pattern.hasMatch(source),
            isFalse,
            reason: '$path 命中禁止的网络上传模式: ${pattern.pattern}\n'
                '摄像头帧禁止上传到任何服务器(AGENTS.md §3)',
          );
        }
      });
    }
  });

  group('表情识别隐私审计 - lite_rt 服务源码包含明确隐私注释', () {
    test('LiteRt 服务源码注释中明确声明"不上传图像数据"', () {
      final source = File(
        'lib/data/services/lite_rt_expression_recognition_service.dart',
      ).readAsStringSync();

      // 注释中应明确声明隐私保证
      expect(
        source.contains('不上传'),
        isTrue,
        reason: 'LiteRt 服务应明确注释"不上传图像数据"',
      );
      expect(
        source.contains('不写入文件') || source.contains('不写入文件系统'),
        isTrue,
        reason: 'LiteRt 服务应明确注释"不写入文件系统"',
      );
    });

    test('LiteRt 服务源码注释中明确声明科学边界 (不诊断)', () {
      final source = File(
        'lib/data/services/lite_rt_expression_recognition_service.dart',
      ).readAsStringSync();

      expect(
        source.contains('不进行心理诊断'),
        isTrue,
        reason: 'LiteRt 服务应明确注释"不进行心理诊断"',
      );
      expect(
        source.contains('unknown') || source.contains('低置信度'),
        isTrue,
        reason: 'LiteRt 服务应处理低置信度场景,不强行判断表情',
      );
    });
  });

  group('表情识别隐私审计 - 学习陪伴页面不引入文件保存', () {
    test('study_companion_page.dart 不包含文件写入或上传调用', () {
      final file = File(
          'lib/features/study_companion/presentation/study_companion_page.dart',);
      expect(file.existsSync(), isTrue);
      final source = file.readAsStringSync();

      for (final pattern in [
        ..._forbiddenFileWritePatterns,
        ..._forbiddenNetworkPatterns,
      ]) {
        expect(
          pattern.hasMatch(source),
          isFalse,
          reason: 'study_companion_page 命中禁止模式: ${pattern.pattern}',
        );
      }
    });

    test('expression_panel.dart 不包含文件写入或上传调用', () {
      final file = File(
          'lib/features/study_companion/presentation/widgets/expression_panel.dart',);
      expect(file.existsSync(), isTrue);
      final source = file.readAsStringSync();

      for (final pattern in [
        ..._forbiddenFileWritePatterns,
        ..._forbiddenNetworkPatterns,
      ]) {
        expect(
          pattern.hasMatch(source),
          isFalse,
          reason: 'expression_panel 命中禁止模式: ${pattern.pattern}',
        );
      }
    });
  });
}
