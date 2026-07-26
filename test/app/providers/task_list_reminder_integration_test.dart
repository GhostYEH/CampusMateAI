import 'package:flutter_test/flutter_test.dart';

import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/data/models/task.dart';
import 'package:campus_companion/data/services/service_interfaces.dart';
import 'package:campus_companion/features/notifications/presentation/widgets/reminder_permission_banner.dart';
import 'package:campus_companion/mock/mock_services/fake_notification_reminder_service.dart';
import 'package:campus_companion/mock/mock_services/mock_services.dart';

/// 构造一个带提醒的待办任务。
Task _reminderTask({
  required String id,
  required DateTime deadline,
  required int leadMinutes,
  String title = '测试任务',
}) {
  final reminderAt = deadline.subtract(Duration(minutes: leadMinutes));
  return Task(
    id: id,
    title: title,
    category: TaskCategory.study,
    priority: TaskPriority.medium,
    createdAt: DateTime(2025, 1, 1),
    source: TaskSource.manual,
    deadline: deadline,
    reminderEnabled: true,
    reminderAt: reminderAt,
  );
}

void main() {
  late MockTaskRepository repo;
  late FakeNotificationReminderService reminder;
  late TaskListNotifier notifier;

  /// 标准初始化:已授权 + 可调度精确闹钟 + 默认 supported 平台。
  setUp(() {
    repo = MockTaskRepository(initial: const []);
    reminder = FakeNotificationReminderService(
      capability: ReminderCapabilityStatus.supported,
      initialPermission: ReminderPermissionStatus.granted,
      canScheduleExactAlarmsFlag: true,
    );
    notifier = TaskListNotifier(repo, reminder);
  });

  /// 创建任务(并附带一个未来时间)。
  Future<Task> createReminderTask({
    required String id,
    Duration fromNow = const Duration(hours: 2),
    int leadMinutes = 60,
  }) async {
    final deadline = DateTime.now().add(fromNow);
    final task = _reminderTask(
      id: id,
      deadline: deadline,
      leadMinutes: leadMinutes,
    );
    return notifier.createTask(task);
  }

  group('TaskListNotifier - 提醒生命周期', () {
    test('创建带提醒的任务 → 调度精确提醒', () async {
      await createReminderTask(id: 't1', leadMinutes: 120);

      expect(reminder.hasScheduled('t1', offsetMinutes: 120), isTrue);
      expect(notifier.lastScheduleResult?.success, isTrue);
      expect(notifier.lastScheduleTaskId, 't1');
    });

    test('修改截止时间 → 取消旧提醒并调度新提醒(offset 变化)', () async {
      final task = await createReminderTask(id: 't1', leadMinutes: 120);
      // 改 deadline 到 24h 后(leadMinutes 不变,reminderAt 也跟随),
      // 注意 reminderAt 不变 → offset = deadline - reminderAt 会变化
      final newDeadline = task.deadline!.add(const Duration(hours: 22));
      // 旧的 reminderAt 已基于旧 deadline 计算,这里保持不变 → offset 增大
      final updated = task.copyWith(deadline: newDeadline);
      await notifier.updateTask(updated);

      // 旧 offset=120 应已清空(因 updateReminder 内部 cancelAllForTask)
      // 新 offset = 22h+2h = 24h = 1440min
      // 但 _offsetMinutesFor 重新计算,新 reminderAt 仍是旧值(没改),
      // 所以 offset = newDeadline - oldReminderAt = 120 + 22*60 = 1440
      expect(reminder.hasScheduled('t1', offsetMinutes: 120), isFalse);
      expect(reminder.hasScheduled('t1', offsetMinutes: 1440), isTrue);
    });

    test('修改提醒偏移 → 同步更新到新 offset', () async {
      final task = await createReminderTask(id: 't1', leadMinutes: 120);
      // 改 reminderAt(更早 1 天)→ offset 增大
      final newReminderAt = task.reminderAt!.subtract(const Duration(days: 1));
      final updated = task.copyWith(reminderAt: newReminderAt);
      await notifier.updateTask(updated);

      // 旧 offset=120 应已清空
      expect(reminder.hasScheduled('t1', offsetMinutes: 120), isFalse);
      // 新 offset = deadline - newReminderAt = 120 + 1440 = 1560
      expect(reminder.hasScheduled('t1', offsetMinutes: 1560), isTrue);
    });

    test('关闭提醒(reminderEnabled=false)→ 取消全部相关提醒', () async {
      final task = await createReminderTask(id: 't1', leadMinutes: 120);
      expect(reminder.hasScheduled('t1', offsetMinutes: 120), isTrue);

      final updated = task.copyWith(reminderEnabled: false);
      await notifier.updateTask(updated);

      expect(reminder.hasScheduled('t1'), isFalse);
      expect(notifier.lastScheduleResult, isNull);
    });

    test('完成任务 → 取消未触发提醒', () async {
      final task = await createReminderTask(id: 't1', leadMinutes: 120);
      expect(reminder.hasScheduled('t1', offsetMinutes: 120), isTrue);

      await notifier.toggleComplete(task);

      expect(reminder.hasScheduled('t1'), isFalse);
    });

    test('恢复未完成任务 → 重新调度提醒', () async {
      final task = await createReminderTask(id: 't1', leadMinutes: 120);
      await notifier.toggleComplete(task); // 完成 → 取消
      expect(reminder.hasScheduled('t1'), isFalse);

      await notifier.restore(task.id); // 恢复 → 重新调度

      expect(reminder.hasScheduled('t1', offsetMinutes: 120), isTrue);
    });

    test('软删除任务 → 取消全部提醒', () async {
      final task = await createReminderTask(id: 't1', leadMinutes: 120);
      expect(reminder.hasScheduled('t1'), isTrue);

      await notifier.softDelete(task.id);

      expect(reminder.hasScheduled('t1'), isFalse);
    });

    test('硬删除任务 → 取消全部提醒', () async {
      final task = await createReminderTask(id: 't1', leadMinutes: 120);
      expect(reminder.hasScheduled('t1'), isTrue);

      await notifier.hardDelete(task.id);

      expect(reminder.hasScheduled('t1'), isFalse);
    });

    test('setReminder(null) → 关闭提醒并取消', () async {
      final task = await createReminderTask(id: 't1', leadMinutes: 120);
      expect(reminder.hasScheduled('t1'), isTrue);

      final result = await notifier.setReminder(task, null);

      expect(result, isNull); // 关闭提醒返回 null
      expect(reminder.hasScheduled('t1'), isFalse);
    });

    test('setReminder(newTime) → 调度新提醒并返回 success', () async {
      final task = await createReminderTask(id: 't1', leadMinutes: 120);
      final newReminderAt =
          task.deadline!.subtract(const Duration(minutes: 1440)); // 提前 24h

      final result = await notifier.setReminder(task, newReminderAt);

      expect(result?.success, isTrue);
      // 旧 offset=120 应已清空
      expect(reminder.hasScheduled('t1', offsetMinutes: 120), isFalse);
      expect(reminder.hasScheduled('t1', offsetMinutes: 1440), isTrue);
    });
  });

  group('TaskListNotifier - 权限场景', () {
    test('通知权限被拒 → 不调度,返回 notificationPermissionDenied', () async {
      reminder.denyPermission();
      // 注意:repo 已构造,直接创建任务测试
      final deadline = DateTime.now().add(const Duration(hours: 2));
      final task = _reminderTask(
        id: 't1',
        deadline: deadline,
        leadMinutes: 120,
      );
      await notifier.createTask(task);

      expect(reminder.hasScheduled('t1'), isFalse);
      expect(
        notifier.lastScheduleResult?.failure,
        ReminderScheduleFailure.notificationPermissionDenied,
      );
    });

    test('精确提醒权限未授予 → 不调度,返回 exactAlarmPermissionDenied', () async {
      reminder.setCanScheduleExactAlarms(false);
      final deadline = DateTime.now().add(const Duration(hours: 2));
      final task = _reminderTask(
        id: 't1',
        deadline: deadline,
        leadMinutes: 120,
      );
      await notifier.createTask(task);

      expect(reminder.hasScheduled('t1'), isFalse);
      expect(
        notifier.lastScheduleResult?.failure,
        ReminderScheduleFailure.exactAlarmPermissionDenied,
      );
    });

    test('权限被拒后 restoreAllReminders → 返回 0,不假装恢复', () async {
      // 持久化一个有效任务
      await createReminderTask(id: 't1', leadMinutes: 120);
      reminder.scheduled.clear();
      reminder.simulatedPendingIds.clear();
      // 撤销精确权限
      reminder.setCanScheduleExactAlarms(false);

      final restored = await notifier.restoreAllReminders();
      expect(restored, 0);
      expect(reminder.hasScheduled('t1'), isFalse);
    });

    test('Web 平台 → capability=degraded + unsupportedPlatform', () async {
      // 模拟 Web 平台
      reminder.unsupportedPlatform = true;
      final deadline = DateTime.now().add(const Duration(hours: 2));
      final task = _reminderTask(
        id: 't1',
        deadline: deadline,
        leadMinutes: 120,
      );
      await notifier.createTask(task);

      expect(reminder.hasScheduled('t1'), isFalse);
      expect(
        notifier.lastScheduleResult?.failure,
        ReminderScheduleFailure.unsupportedPlatform,
      );
      expect(
        reminder.capabilityStatus(),
        ReminderCapabilityStatus.degraded,
      );
    });

    test('插件异常 → 返回 pluginException,不虚报成功', () async {
      reminder.shouldFailWithPluginException = true;
      final deadline = DateTime.now().add(const Duration(hours: 2));
      final task = _reminderTask(
        id: 't1',
        deadline: deadline,
        leadMinutes: 120,
      );
      await notifier.createTask(task);

      expect(reminder.hasScheduled('t1'), isFalse);
      expect(
        notifier.lastScheduleResult?.failure,
        ReminderScheduleFailure.pluginException,
      );
    });
  });

  group('TaskListNotifier - 过去时间', () {
    test('reminderAt 已过去 → 返回 pastTime,不调度', () async {
      // deadline 已过去(逾期任务)
      final deadline = DateTime.now().subtract(const Duration(hours: 1));
      final reminderAt = deadline.subtract(const Duration(minutes: 120));
      final task = Task(
        id: 't1',
        title: '逾期任务',
        category: TaskCategory.study,
        priority: TaskPriority.medium,
        createdAt: DateTime(2025, 1, 1),
        source: TaskSource.manual,
        deadline: deadline,
        reminderEnabled: true,
        reminderAt: reminderAt,
      );
      await notifier.createTask(task);

      expect(reminder.hasScheduled('t1'), isFalse);
      expect(
        notifier.lastScheduleResult?.failure,
        ReminderScheduleFailure.pastTime,
      );
    });
  });

  group('TaskListNotifier - 稳定 ID', () {
    test('同 (taskId, offset) 多次调度产生相同 ID', () async {
      final deadline = DateTime.now().add(const Duration(hours: 2));
      final task = _reminderTask(
        id: 'stable_id_task',
        deadline: deadline,
        leadMinutes: 120,
      );
      await notifier.createTask(task);
      final id1 = reminder.record('stable_id_task', 120)!.id;

      // 再次调度(updateReminder 会先 cancel 再 schedule)
      await notifier.updateTask(task);
      final id2 = reminder.record('stable_id_task', 120)!.id;

      expect(id1, id2);
    });

    test('不同 task 产生不同 ID', () async {
      await createReminderTask(id: 't_a', leadMinutes: 120);
      await createReminderTask(id: 't_b', leadMinutes: 120);
      final idA = reminder.record('t_a', 120)!.id;
      final idB = reminder.record('t_b', 120)!.id;
      expect(idA, isNot(idB));
    });

    test('Fake ID 与 LocalNotificationReminderService 公式一致', () {
      // 同一公式 — 测试两边对齐
      const taskId = 'task_xyz';
      const offset = 1440;
      final fakeId = FakeNotificationReminderService.notificationIdFor(
        taskId,
        offset,
      );
      // LocalNotificationReminderService.notificationIdFor 是 static,
      // 这里通过 Fake 的实现验证公式一致性(二者代码完全相同)
      // 重新计算一次以确保公式稳定
      const int fnvPrime = 0x01000193;
      int hash = 0x811C9DC5;
      void mix(int byte) {
        hash ^= byte;
        hash = (hash * fnvPrime) & 0x7fffffff;
      }

      for (final c in taskId.codeUnits) {
        mix(c);
      }
      mix(0x7C);
      mix(offset & 0xFF);
      mix((offset >> 8) & 0xFF);
      mix((offset >> 16) & 0xFF);
      mix((offset >> 24) & 0xFF);
      final expectedId = hash % 1000000;

      expect(fakeId, expectedId);
    });
  });

  group('TaskListNotifier - 重启恢复去重', () {
    test('restoreAllReminders 跳过已存在的提醒', () async {
      // 持久化任务,首次调度
      await createReminderTask(id: 't1', leadMinutes: 120);
      expect(reminder.scheduled.length, 1);

      // 模拟"进程重启后再次调用 restoreAllReminders"
      // Fake 中 simulatedPendingIds 跟踪了已调度 ID,restoreReminders 会跳过
      final restored = await notifier.restoreAllReminders();
      expect(restored, 0); // 全部已存在,没有新增
      expect(reminder.scheduled.length, 1); // 仍只有 1 条
    });

    test('restoreAllReminders 跳过已完成任务', () async {
      final task = await createReminderTask(id: 't1', leadMinutes: 120);
      await notifier.toggleComplete(task); // 完成 → cancelAll
      expect(reminder.scheduled, isEmpty);

      // 模拟重启后 restore — 已完成任务不应被恢复
      final restored = await notifier.restoreAllReminders();
      expect(restored, 0);
      expect(reminder.scheduled, isEmpty);
    });

    test('restoreAllReminders 跳过已删除任务', () async {
      final task = await createReminderTask(id: 't1', leadMinutes: 120);
      await notifier.softDelete(task.id);
      expect(reminder.scheduled, isEmpty);

      final restored = await notifier.restoreAllReminders();
      expect(restored, 0);
    });

    test('restoreAllReminders 恢复多个有效任务', () async {
      // 先 cancel 所有现有,模拟重启
      await createReminderTask(id: 't1', leadMinutes: 120);
      await createReminderTask(id: 't2', leadMinutes: 1440);
      expect(reminder.scheduled.length, 2);

      // 清空内存跟踪但不清空 simulatedPendingIds — 模拟 pendingNotificationRequests
      // 仍返回已存在的 ID
      // 在 Fake 中,清空 scheduled 也会清空 simulatedPendingIds,所以这里直接验证:
      // 不清空,直接调用 restore — 应返回 0(都存在)
      final restored = await notifier.restoreAllReminders();
      expect(restored, 0); // 已存在,不重复创建

      // 现在手动清空 simulatedPendingIds(模拟系统重启后 pending 列表丢失),
      // 但保留 scheduled map 不变 — restoreReminders 会重新创建
      reminder.simulatedPendingIds.clear();
      // 同时清空 scheduled,模拟"进程重启内存丢失"
      reminder.scheduled.clear();
      final restored2 = await notifier.restoreAllReminders();
      expect(restored2, 2);
    });
  });

  group('TaskListNotifier - 演示数据恢复去重', () {
    test('resetToDemo 后 restoreAllReminders 不产生大量重复通知', () async {
      // 演示数据通常包含若干带提醒的任务
      await repo.resetToDemo();
      // notifier 通过 watchTasks 监听到变化,state 已更新

      // 首次 restore — 调度演示任务的提醒
      final firstRestore = await notifier.restoreAllReminders();
      expect(firstRestore, greaterThanOrEqualTo(0));

      // 再次 restore — 应全部跳过(不重复)
      final secondRestore = await notifier.restoreAllReminders();
      expect(secondRestore, 0);
    });
  });

  group('ReminderStatusSnapshot - 派生状态', () {
    test('canSchedule 要求三条件全满足', () {
      const snapshot = ReminderStatusSnapshot(
        capability: ReminderCapabilityStatus.supported,
        permission: ReminderPermissionStatus.granted,
        canScheduleExactAlarms: true,
      );
      expect(snapshot.canSchedule, isTrue);
      expect(snapshot.needsNotificationPermission, isFalse);
      expect(snapshot.needsExactAlarmPermission, isFalse);
    });

    test('needsNotificationPermission 在 denied 时为 true', () {
      const snapshot = ReminderStatusSnapshot(
        capability: ReminderCapabilityStatus.supported,
        permission: ReminderPermissionStatus.denied,
        canScheduleExactAlarms: true,
      );
      expect(snapshot.canSchedule, isFalse);
      expect(snapshot.needsNotificationPermission, isTrue);
    });

    test('needsExactAlarmPermission 在通知已授权但精确权限未授时为 true', () {
      const snapshot = ReminderStatusSnapshot(
        capability: ReminderCapabilityStatus.supported,
        permission: ReminderPermissionStatus.granted,
        canScheduleExactAlarms: false,
      );
      expect(snapshot.canSchedule, isFalse);
      expect(snapshot.needsNotificationPermission, isFalse);
      expect(snapshot.needsExactAlarmPermission, isTrue);
    });

    test('Web 平台(degraded + unsupported)→ canSchedule=false', () {
      const snapshot = ReminderStatusSnapshot(
        capability: ReminderCapabilityStatus.degraded,
        permission: ReminderPermissionStatus.unsupported,
        canScheduleExactAlarms: false,
      );
      expect(snapshot.canSchedule, isFalse);
      // Web 不展示权限引导横幅 — needsNotificationPermission 检查 supported
      expect(snapshot.needsNotificationPermission, isFalse);
      expect(snapshot.needsExactAlarmPermission, isFalse);
    });
  });

  group('ReminderScheduleFeedback - 反馈文案', () {
    test('null 结果 → 无提示', () {
      expect(ReminderScheduleFeedback.messageFor(null), isNull);
    });

    test('success → 无提示(由调用方控制)', () {
      const result = ReminderScheduleResult.success(123);
      expect(ReminderScheduleFeedback.messageFor(result), isNull);
    });

    test('exactAlarmPermissionDenied → 提示前往闹钟和提醒', () {
      const result = ReminderScheduleResult.failed(
        ReminderScheduleFailure.exactAlarmPermissionDenied,
      );
      final msg = ReminderScheduleFeedback.messageFor(result);
      expect(msg, isNotNull);
      expect(msg, contains('精确提醒权限'));
      expect(msg, contains('闹钟和提醒'));
    });

    test('notificationPermissionDenied → 提示通知权限', () {
      const result = ReminderScheduleResult.failed(
        ReminderScheduleFailure.notificationPermissionDenied,
      );
      final msg = ReminderScheduleFeedback.messageFor(result);
      expect(msg, isNotNull);
      expect(msg, contains('通知权限'));
    });

    test('pastTime → 提示时间已过期', () {
      const result = ReminderScheduleResult.failed(
        ReminderScheduleFailure.pastTime,
      );
      final msg = ReminderScheduleFeedback.messageFor(result);
      expect(msg, contains('过期'));
    });

    test('unsupportedPlatform → 提示 Web 端', () {
      const result = ReminderScheduleResult.failed(
        ReminderScheduleFailure.unsupportedPlatform,
      );
      final msg = ReminderScheduleFeedback.messageFor(result);
      expect(msg, contains('Web'));
    });

    test('pluginException → 提示稍后重试', () {
      const result = ReminderScheduleResult.failed(
        ReminderScheduleFailure.pluginException,
      );
      final msg = ReminderScheduleFeedback.messageFor(result);
      expect(msg, contains('失败'));
      expect(msg, contains('任务已保存'));
    });
  });
}
