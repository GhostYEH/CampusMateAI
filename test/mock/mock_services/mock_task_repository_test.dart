import 'package:flutter_test/flutter_test.dart';
import 'package:campus_companion/data/models/notice.dart';
import 'package:campus_companion/data/models/task.dart';
import 'package:campus_companion/mock/mock_services/mock_services.dart';

/// 构造一个可控初始任务的仓库。
MockTaskRepository _repoWith(List<Task> initial) =>
    MockTaskRepository(initial: initial);

Task _task({
  required String id,
  String title = '任务',
  TaskCategory category = TaskCategory.other,
  TaskPriority priority = TaskPriority.medium,
  DateTime? deadline,
  bool completed = false,
  bool deleted = false,
}) {
  return Task(
    id: id,
    title: title,
    category: category,
    priority: priority,
    createdAt: DateTime(2025, 1, 1),
    source: TaskSource.manual,
    deadline: deadline,
    completed: completed,
    deleted: deleted,
    completedAt: completed ? DateTime(2025, 1, 2) : null,
  );
}

void main() {
  group('MockTaskRepository - 新增', () {
    test('createTask 后任务出现在 tasks 列表中', () async {
      final repo = _repoWith([]);
      expect(repo.tasks, isEmpty);

      final task = _task(id: 't1', title: '新建任务');
      await repo.createTask(task);

      expect(repo.tasks.length, 1);
      expect(repo.tasks.first.id, 't1');
      expect(repo.tasks.first.title, '新建任务');
    });

    test('createTask 触发 watchTasks 流发射', () async {
      final repo = _repoWith([]);
      final emitted = <List<Task>>[];
      final sub = repo.watchTasks().listen(emitted.add);

      await repo.createTask(_task(id: 't1'));
      // 等待异步发射
      await Future.delayed(const Duration(milliseconds: 20));

      expect(emitted, isNotEmpty);
      expect(emitted.last.any((t) => t.id == 't1'), isTrue);
      await sub.cancel();
    });
  });

  group('MockTaskRepository - 完成 / 更新', () {
    test('updateTask 切换完成状态', () async {
      final repo = _repoWith([_task(id: 't1', completed: false)]);

      final original = repo.tasks.first;
      expect(original.completed, isFalse);

      await repo.updateTask(
        original.copyWith(
          completed: true,
          completedAt: DateTime(2025, 1, 5),
        ),
      );

      expect(repo.tasks.first.completed, isTrue);
      expect(repo.tasks.first.completedAt, DateTime(2025, 1, 5));
    });

    test('getCompleted 仅返回已完成任务', () async {
      final repo = _repoWith([
        _task(id: 't1', completed: true),
        _task(id: 't2', completed: false),
        _task(id: 't3', completed: true),
      ]);

      final completed = await repo.getCompleted();
      expect(completed.length, 2);
      expect(completed.every((t) => t.completed), isTrue);
    });
  });

  group('MockTaskRepository - 软删除 / 恢复 / 硬删除', () {
    test('softDelete 标记 deleted=true 后不出现在 tasks', () async {
      final repo = _repoWith([_task(id: 't1'), _task(id: 't2')]);

      await repo.softDelete('t1');
      expect(repo.tasks.length, 1);
      expect(repo.tasks.first.id, 't2');
    });

    test('restore 恢复软删除的任务', () async {
      final repo = _repoWith([_task(id: 't1')]);
      await repo.softDelete('t1');
      expect(repo.tasks, isEmpty);

      await repo.restore('t1');
      expect(repo.tasks.length, 1);
      expect(repo.tasks.first.id, 't1');
      expect(repo.tasks.first.deleted, isFalse);
    });

    test('hardDelete 彻底移除任务(不可恢复)', () async {
      final repo = _repoWith([_task(id: 't1')]);

      await repo.hardDelete('t1');
      expect(repo.tasks, isEmpty);

      // 恢复已硬删除的任务应无效
      await repo.restore('t1');
      expect(repo.tasks, isEmpty);
    });

    test('对不存在的 ID 操作不抛异常', () async {
      final repo = _repoWith([]);
      await repo.softDelete('not_exist');
      await repo.restore('not_exist');
      await repo.hardDelete('not_exist');
      await repo.updateTask(_task(id: 'not_exist'));
      expect(repo.tasks, isEmpty);
    });
  });

  group('MockTaskRepository - 查询', () {
    test('getByCategory 按类别过滤', () async {
      final repo = _repoWith([
        _task(id: 't1', category: TaskCategory.study),
        _task(id: 't2', category: TaskCategory.scholarship),
        _task(id: 't3', category: TaskCategory.study),
      ]);

      final study = await repo.getByCategory(TaskCategory.study);
      expect(study.length, 2);
      expect(study.every((t) => t.category == TaskCategory.study), isTrue);
    });

    test('getUpcoming 仅返回未完成且有截止时间,按截止升序', () async {
      final now = DateTime.now();
      final repo = _repoWith([
        _task(id: 't1', deadline: now.add(const Duration(days: 5))),
        _task(id: 't2', deadline: now.add(const Duration(days: 1))),
        _task(id: 't3', deadline: now.add(const Duration(days: 3))),
        _task(id: 't4', deadline: null),
        _task(
          id: 't5',
          deadline: now.add(const Duration(days: 2)),
          completed: true,
        ),
      ]);

      final upcoming = await repo.getUpcoming();
      expect(upcoming.length, 3); // 排除无截止 + 已完成
      expect(upcoming[0].id, 't2'); // 1天后
      expect(upcoming[1].id, 't3'); // 3天后
      expect(upcoming[2].id, 't1'); // 5天后
    });

    test('getToday 仅返回今日截止且未完成', () async {
      final now = DateTime.now();
      final today = DateTime(now.year, now.month, now.day, 23, 59);
      final repo = _repoWith([
        _task(id: 't1', deadline: today),
        _task(id: 't2', deadline: today.add(const Duration(days: 1))),
        _task(id: 't3', deadline: today, completed: true),
      ]);

      final result = await repo.getToday();
      expect(result.length, 1);
      expect(result.first.id, 't1');
    });

    test('tasks 排序: 未完成在前,截止近的在前', () {
      final now = DateTime.now();
      final repo = _repoWith([
        _task(id: 'later', deadline: now.add(const Duration(days: 10))),
        _task(
          id: 'done',
          deadline: now.add(const Duration(days: 1)),
          completed: true,
        ),
        _task(id: 'soon', deadline: now.add(const Duration(days: 2))),
      ]);

      // 排序后:soon(未完成+近) > later(未完成+远) > done(已完成)
      expect(repo.tasks[0].id, 'soon');
      expect(repo.tasks[1].id, 'later');
      expect(repo.tasks[2].id, 'done');
    });

    test('tasks 排除软删除任务', () {
      final repo = _repoWith([
        _task(id: 't1'),
        _task(id: 't2', deleted: true),
        _task(id: 't3'),
      ]);
      expect(repo.tasks.length, 2);
      expect(repo.tasks.any((t) => t.id == 't2'), isFalse);
    });
  });

  group('MockTaskRepository - 软删除流发射', () {
    test('softDelete / restore 都触发 watchTasks 发射', () async {
      final repo = _repoWith([_task(id: 't1')]);
      final emitted = <List<Task>>[];
      final sub = repo.watchTasks().listen(emitted.add);

      await repo.softDelete('t1');
      await Future.delayed(const Duration(milliseconds: 10));
      final afterDelete = emitted.length;

      await repo.restore('t1');
      await Future.delayed(const Duration(milliseconds: 10));
      expect(emitted.length, greaterThan(afterDelete));

      await sub.cancel();
    });
  });

  group('Task 模型 - materialProgress', () {
    test('空材料列表进度为 1', () {
      final task = _task(id: 't1');
      expect(task.materialProgress, 1.0);
    });

    test('全部必需材料完成时进度为 1', () {
      final task = Task(
        id: 't1',
        title: 't',
        category: TaskCategory.other,
        priority: TaskPriority.medium,
        createdAt: DateTime(2025, 1, 1),
        source: TaskSource.manual,
        materials: const [
          TaskMaterial(id: 'm1', name: 'A', done: true),
          TaskMaterial(id: 'm2', name: 'B', done: true),
        ],
      );
      expect(task.materialProgress, 1.0);
    });

    test('部分完成按比例计算', () {
      final task = Task(
        id: 't1',
        title: 't',
        category: TaskCategory.other,
        priority: TaskPriority.medium,
        createdAt: DateTime(2025, 1, 1),
        source: TaskSource.manual,
        materials: const [
          TaskMaterial(id: 'm1', name: 'A', done: true),
          TaskMaterial(id: 'm2', name: 'B', done: false),
          TaskMaterial(id: 'm3', name: 'C', done: false, required: false),
        ],
      );
      // 必需材料 2 个,完成 1 个 => 0.5
      expect(task.materialProgress, 0.5);
    });
  });
}
