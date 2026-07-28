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

    group('toContextJson', () {
      test('空上下文返回空 Map(普通入口不发送无关字段)', () {
        const ctx = CounselorContext();
        final json = ctx.toContextJson();
        expect(json, isEmpty);
      });

      test('仅 courseId 时只包含 course_id 字段', () {
        const ctx = CounselorContext(courseId: 'c_001');
        final json = ctx.toContextJson();
        expect(json, {'course_id': 'c_001'});
      });

      test('所有多角色上下文字段都被序列化', () {
        const ctx = CounselorContext(
          courseId: 'c_001',
          classId: 'cls_101',
          assignmentId: 'a_001',
          announcementId: 'an_001',
          studySessionId: 'ss_001',
          selfReport: '有些疲惫',
        );
        final json = ctx.toContextJson();
        expect(json['course_id'], 'c_001');
        expect(json['class_id'], 'cls_101');
        expect(json['assignment_id'], 'a_001');
        expect(json['announcement_id'], 'an_001');
        expect(json['study_session_id'], 'ss_001');
        expect(json['self_report'], '有些疲惫');
        // contextLabel 不应发送给后端(仅 UI 用)
        expect(json.containsKey('context_label'), isFalse);
        expect(json.containsKey('context_title'), isFalse);
      });

      test('expression_signal 被序列化为 Map', () {
        const ctx = CounselorContext(
          expressionSignal: {'label': 'sad', 'confidence': 0.8},
        );
        final json = ctx.toContextJson();
        expect(json['expression_signal'], isA<Map>());
        expect((json['expression_signal'] as Map)['label'], 'sad');
      });

      test('recent_tasks 被序列化为 List<Map>', () {
        const ctx = CounselorContext(
          recentTasks: [
            CounselorRecentTask(
              id: 't_001',
              title: '提交实验报告',
              deadline: '2026-09-20T23:59:59',
              priority: 'high',
              status: 'pending',
            ),
          ],
        );
        final json = ctx.toContextJson();
        expect(json['recent_tasks'], isA<List>());
        final list = json['recent_tasks'] as List;
        expect(list.length, 1);
        expect(list.first['id'], 't_001');
        expect(list.first['title'], '提交实验报告');
        expect(list.first['deadline'], '2026-09-20T23:59:59');
        expect(list.first['priority'], 'high');
        expect(list.first['status'], 'pending');
      });

      test('空 recentTasks 不产生 recent_tasks 字段', () {
        const ctx = CounselorContext(courseId: 'c_001');
        final json = ctx.toContextJson();
        expect(json.containsKey('recent_tasks'), isFalse);
      });
    });
  });

  group('CounselorRecentTask', () {
    test('toJson 只包含必要字段(id/title/deadline/priority/status)', () {
      const task = CounselorRecentTask(
        id: 't_001',
        title: '提交实验报告',
        deadline: '2026-09-20T23:59:59',
        priority: 'high',
        status: 'pending',
      );
      final json = task.toJson();
      expect(json.keys.toSet(), {'id', 'title', 'deadline', 'priority', 'status'});
      expect(json['id'], 't_001');
      expect(json['title'], '提交实验报告');
    });

    test('toJson 仅 id/title 必填时只包含这两个字段', () {
      const task = CounselorRecentTask(id: 't_001', title: '任务');
      final json = task.toJson();
      expect(json.keys.toSet(), {'id', 'title'});
    });

    test('Equatable 相等性', () {
      const a = CounselorRecentTask(
        id: 't_001',
        title: 'A',
        deadline: 'd',
        priority: 'high',
        status: 'pending',
      );
      const b = CounselorRecentTask(
        id: 't_001',
        title: 'A',
        deadline: 'd',
        priority: 'high',
        status: 'pending',
      );
      expect(a, equals(b));
      expect(a.hashCode, b.hashCode);
    });
  });

  group('CounselorContext.fromExtra with recent_tasks', () {
    test('从路由 extra 解析 recent_tasks 列表', () {
      final ctx = CounselorContext.fromExtra(const <String, dynamic>{
        'course_id': 'c_001',
        'context_title': '我的待办',
        'recent_tasks': [
          {
            'id': 't_001',
            'title': '提交实验报告',
            'deadline': '2026-09-20T23:59:59',
            'priority': 'high',
            'status': 'pending',
          },
          {
            'id': 't_002',
            'title': '复习高数',
          },
        ],
      });
      expect(ctx.courseId, 'c_001');
      expect(ctx.contextLabel, '我的待办');
      expect(ctx.recentTasks.length, 2);
      expect(ctx.recentTasks[0].id, 't_001');
      expect(ctx.recentTasks[0].title, '提交实验报告');
      expect(ctx.recentTasks[0].deadline, '2026-09-20T23:59:59');
      expect(ctx.recentTasks[0].priority, 'high');
      expect(ctx.recentTasks[0].status, 'pending');
      expect(ctx.recentTasks[1].id, 't_002');
      expect(ctx.recentTasks[1].title, '复习高数');
      expect(ctx.recentTasks[1].deadline, isNull);
      expect(ctx.hasContext, isTrue);
    });

    test('recent_tasks 中 id 为空的条目被过滤', () {
      final ctx = CounselorContext.fromExtra(const <String, dynamic>{
        'recent_tasks': [
          {'id': '', 'title': '空 id 应过滤'},
          {'id': 't_001', 'title': '保留'},
        ],
      });
      expect(ctx.recentTasks.length, 1);
      expect(ctx.recentTasks[0].id, 't_001');
    });

    test('recent_tasks 为非 List 类型时不抛异常,返回空列表', () {
      final ctx = CounselorContext.fromExtra(const <String, dynamic>{
        'recent_tasks': 'not a list',
      });
      expect(ctx.recentTasks, isEmpty);
      // recent_tasks 为空且无其他上下文 → hasContext 为 false
      expect(ctx.hasContext, isFalse);
    });
  });
}
