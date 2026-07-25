import 'package:flutter_test/flutter_test.dart';
import 'package:campus_companion/data/models/notice.dart';

void main() {
  group('NoticeImportance', () {
    test('fromString 解析中英文标签', () {
      expect(NoticeImportance.fromString('urgent'), NoticeImportance.urgent);
      expect(NoticeImportance.fromString('紧急'), NoticeImportance.urgent);
      expect(
        NoticeImportance.fromString('important'),
        NoticeImportance.important,
      );
      expect(NoticeImportance.fromString('重要'), NoticeImportance.important);
      expect(NoticeImportance.fromString('normal'), NoticeImportance.normal);
      expect(NoticeImportance.fromString('普通'), NoticeImportance.normal);
      expect(NoticeImportance.fromString('一般'), NoticeImportance.normal);
      expect(NoticeImportance.fromString(null), NoticeImportance.unknown);
      expect(NoticeImportance.fromString('unknown'), NoticeImportance.unknown);
    });

    test('weight 排序: urgent > important > normal > unknown', () {
      expect(
        NoticeImportance.urgent.weight,
        greaterThan(NoticeImportance.important.weight),
      );
      expect(
        NoticeImportance.important.weight,
        greaterThan(NoticeImportance.normal.weight),
      );
      expect(
        NoticeImportance.normal.weight,
        greaterThan(NoticeImportance.unknown.weight),
      );
    });
  });

  group('TaskMaterial', () {
    test('copyWith 仅修改指定字段', () {
      const m = TaskMaterial(id: 'm1', name: '申请表');
      final updated = m.copyWith(done: true, note: '已签字');
      expect(updated.id, 'm1');
      expect(updated.name, '申请表');
      expect(updated.done, isTrue);
      expect(updated.note, '已签字');
      expect(updated.required, isTrue); // 默认值保持
    });

    test('toJson / fromJson 往返一致', () {
      const m = TaskMaterial(
        id: 'm1',
        name: '证明材料',
        required: false,
        done: true,
        note: '盖章版',
      );
      final json = m.toJson();
      final restored = TaskMaterial.fromJson(json);
      expect(restored, m);
    });

    test('fromJson 缺失字段时使用默认值', () {
      final restored = TaskMaterial.fromJson(const {'id': 'm2', 'name': '成绩单'});
      expect(restored.id, 'm2');
      expect(restored.name, '成绩单');
      expect(restored.required, isTrue);
      expect(restored.done, isFalse);
      expect(restored.note, isNull);
    });

    test('相等性基于全部字段', () {
      const a = TaskMaterial(id: 'm1', name: 'A');
      const b = TaskMaterial(id: 'm1', name: 'A');
      const c = TaskMaterial(id: 'm1', name: 'B');
      expect(a, equals(b));
      expect(a, isNot(equals(c)));
    });
  });

  group('ExtractedNotice', () {
    test('completeness 字段完成度评分', () {
      // 全空: 1/6 (taskName 默认非空)
      const empty = ExtractedNotice(taskName: '测试任务');
      // taskName 已填,其他 5 项空 => 1/6
      expect(empty.completeness, closeTo(1 / 6, 1e-6));

      // 全填: 6/6 = 1
      final full = ExtractedNotice(
        taskName: '提交实践申请',
        targetAudience: '2024级',
        deadline: DateTime(2025, 10, 20),
        materials: const [TaskMaterial(id: 'm', name: '申请表')],
        submitMethod: '纸质版提交',
        location: '行政楼302',
      );
      expect(full.completeness, 1.0);

      // 部分: taskName + deadline = 2/6
      final partial = ExtractedNotice(
        taskName: '任务',
        deadline: DateTime(2025, 10, 20),
      );
      expect(partial.completeness, closeTo(2 / 6, 1e-6));
    });

    test('copyWith 不影响原对象(不可变性)', () {
      const original = ExtractedNotice(
        taskName: '原任务',
        importance: NoticeImportance.normal,
        confidence: 0.5,
      );
      final updated = original.copyWith(
        taskName: '新任务',
        importance: NoticeImportance.urgent,
      );
      expect(original.taskName, '原任务');
      expect(original.importance, NoticeImportance.normal);
      expect(updated.taskName, '新任务');
      expect(updated.importance, NoticeImportance.urgent);
      // 未修改的字段保持
      expect(updated.confidence, 0.5);
    });

    test('materials 空列表与null 语义区分', () {
      const withMaterials = ExtractedNotice(
        taskName: 't',
        materials: [TaskMaterial(id: 'm', name: '材料')],
      );
      const withoutMaterials = ExtractedNotice(taskName: 't');
      expect(
        withMaterials.completeness,
        greaterThan(withoutMaterials.completeness),
      );
    });
  });

  group('CampusNotice', () {
    test('copyWith 标记已读不影响其他字段', () {
      final notice = CampusNotice(
        id: 'n1',
        title: '通知标题',
        source: '教务处',
        publishedAt: DateTime(2025, 10, 1),
        content: '正文',
        tags: const ['实践'],
      );
      expect(notice.read, isFalse);

      final read = notice.copyWith(read: true);
      expect(read.read, isTrue);
      expect(read.id, 'n1');
      expect(read.title, '通知标题');
      expect(read.tags, ['实践']);
      // 原对象不变
      expect(notice.read, isFalse);
    });
  });
}
