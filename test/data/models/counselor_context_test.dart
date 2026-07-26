import 'package:flutter_test/flutter_test.dart';

import 'package:campus_companion/data/models/chat.dart';

/// CounselorContext 单元测试 — 验证 AI 导员上下文融合的数据基础。
///
/// 覆盖 AGENTS.md §7 — 学生从课程/通知/任务进入 AI 导员时,
/// 携带 course_id / class_id / assignment_id / announcement_id 上下文。
void main() {
  group('CounselorContext', () {
    test('默认构造为空上下文,hasContext 为 false', () {
      const ctx = CounselorContext();
      expect(ctx.hasContext, isFalse);
      expect(ctx.courseId, isNull);
      expect(ctx.classId, isNull);
      expect(ctx.assignmentId, isNull);
      expect(ctx.announcementId, isNull);
      expect(ctx.contextLabel, isNull);
    });

    test('仅 courseId 时 hasContext 为 true', () {
      const ctx = CounselorContext(
        courseId: 'c_001',
        contextLabel: '高等数学',
      );
      expect(ctx.hasContext, isTrue);
      expect(ctx.courseId, 'c_001');
      expect(ctx.contextLabel, '高等数学');
    });

    test('assignmentId 与 classId 同时存在时 hasContext 为 true', () {
      const ctx = CounselorContext(
        courseId: 'c_001',
        classId: 'cls_101',
        assignmentId: 'a_001',
        contextLabel: '高等数学 · 第 3 次作业',
      );
      expect(ctx.hasContext, isTrue);
      expect(ctx.assignmentId, 'a_001');
      expect(ctx.classId, 'cls_101');
    });

    test('toConversationId 包含所有非空字段,以冒号分隔', () {
      const ctx = CounselorContext(
        courseId: 'c_001',
        classId: 'cls_101',
        assignmentId: 'a_001',
        announcementId: 'an_001',
      );
      final id = ctx.toConversationId();
      expect(id, contains('conv_main'));
      expect(id, contains('course:c_001'));
      expect(id, contains('class:cls_101'));
      expect(id, contains('assignment:a_001'));
      expect(id, contains('announcement:an_001'));
    });

    test('toConversationId 在空上下文时仍返回 conv_main 前缀', () {
      const ctx = CounselorContext();
      expect(ctx.toConversationId(), 'conv_main');
    });

    test('toConversationId 跳过空字段,不产生多余冒号', () {
      const ctx = CounselorContext(courseId: 'c_only');
      final id = ctx.toConversationId();
      // 不应包含 class / assignment / announcement 段
      expect(id.contains('class:'), isFalse);
      expect(id.contains('assignment:'), isFalse);
      expect(id.contains('announcement:'), isFalse);
      expect(id, 'conv_main:course:c_only');
    });

    group('fromExtra', () {
      test('从 Map<String, dynamic> 构造完整上下文', () {
        final ctx = CounselorContext.fromExtra(const <String, dynamic>{
          'course_id': 'c_001',
          'class_id': 'cls_101',
          'assignment_id': 'a_001',
          'announcement_id': 'an_001',
          'context_title': '高等数学 · 第 3 次作业',
        });
        expect(ctx.courseId, 'c_001');
        expect(ctx.classId, 'cls_101');
        expect(ctx.assignmentId, 'a_001');
        expect(ctx.announcementId, 'an_001');
        expect(ctx.contextLabel, '高等数学 · 第 3 次作业');
        expect(ctx.hasContext, isTrue);
      });

      test('部分字段缺失时只填充非空字段', () {
        final ctx = CounselorContext.fromExtra(const <String, dynamic>{
          'course_id': 'c_001',
          'context_title': '高等数学',
        });
        expect(ctx.courseId, 'c_001');
        expect(ctx.classId, isNull);
        expect(ctx.assignmentId, isNull);
        expect(ctx.announcementId, isNull);
        expect(ctx.contextLabel, '高等数学');
        expect(ctx.hasContext, isTrue);
      });

      test('传 null 时返回空上下文', () {
        final ctx = CounselorContext.fromExtra(null);
        expect(ctx.hasContext, isFalse);
      });

      test('传非 Map 类型(如 String)时返回空上下文,不抛异常', () {
        final ctx = CounselorContext.fromExtra('not a map');
        expect(ctx.hasContext, isFalse);
      });

      test('传空 Map 时返回空上下文', () {
        final ctx = CounselorContext.fromExtra(const <String, dynamic>{});
        expect(ctx.hasContext, isFalse);
      });

      test('context_title 缺失时 contextLabel 为 null', () {
        final ctx = CounselorContext.fromExtra(const <String, dynamic>{
          'course_id': 'c_001',
        });
        expect(ctx.contextLabel, isNull);
        expect(ctx.courseId, 'c_001');
      });
    });

    group('Equatable', () {
      test('相同字段值的两个实例相等', () {
        const a = CounselorContext(
          courseId: 'c_001',
          classId: 'cls_101',
          assignmentId: 'a_001',
          announcementId: 'an_001',
          contextLabel: 'label',
        );
        const b = CounselorContext(
          courseId: 'c_001',
          classId: 'cls_101',
          assignmentId: 'a_001',
          announcementId: 'an_001',
          contextLabel: 'label',
        );
        expect(a, equals(b));
        expect(a.hashCode, b.hashCode);
      });

      test('任一字段不同则不相等', () {
        const a = CounselorContext(courseId: 'c_001');
        const b = CounselorContext(courseId: 'c_002');
        expect(a == b, isFalse);
      });
    });
  });
}
