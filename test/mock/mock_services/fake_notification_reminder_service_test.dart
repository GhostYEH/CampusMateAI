import 'package:flutter_test/flutter_test.dart';

import 'package:campus_companion/data/services/service_interfaces.dart';
import 'package:campus_companion/mock/mock_services/fake_notification_reminder_service.dart';

void main() {
  late FakeNotificationReminderService service;

  setUp(() {
    service = FakeNotificationReminderService();
  });

  group('FakeNotificationReminderService - requestPermission', () {
    test('grantPermission() 后 requestPermission 返回 true', () async {
      service.grantPermission();
      final result = await service.requestPermission();
      expect(result, isTrue);
      expect(service.permissionStatus(), ReminderPermissionStatus.granted);
    });

    test('denyPermission() 后 requestPermission 返回 false', () async {
      service.denyPermission();
      final result = await service.requestPermission();
      expect(result, isFalse);
      expect(service.permissionStatus(), ReminderPermissionStatus.denied);
    });

    test('默认未授权状态(notDetermined)requestPermission 返回 true', () async {
      // notDetermined 视为"可请求",首次请求成功(默认 initialPermission=notDetermined)
      final result = await service.requestPermission();
      expect(result, isTrue);
      expect(service.permissionStatus(), ReminderPermissionStatus.granted);
    });

    test('unsupportedPlatform=true 时 requestPermission 返回 false', () async {
      service.unsupportedPlatform = true;
      final result = await service.requestPermission();
      expect(result, isFalse);
      expect(service.permissionStatus(), ReminderPermissionStatus.unsupported);
    });
  });

  group('FakeNotificationReminderService - scheduleReminder', () {
    test('记录调用到 scheduled map 并返回成功', () async {
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      final result = await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: scheduledAt,
      );

      expect(result.success, isTrue);
      expect(result.failure, isNull);
      expect(result.notificationId, isNotNull);
      expect(service.hasScheduled('task_1', 120), isTrue);
      final record = service.scheduled[const ReminderKey('task_1', 120)]!;
      expect(record.title, '待办提醒');
      expect(record.body, '即将截止');
      expect(record.scheduledAt, scheduledAt);
      expect(
        service.calls,
        contains('scheduleReminder:task_1:120'),
      );
    });

    test('已拒绝权限时返回 notificationPermissionDenied 且不记录', () async {
      service.denyPermission();
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      final result = await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: scheduledAt,
      );

      expect(result.success, isFalse);
      expect(
        result.failure,
        ReminderScheduleFailure.notificationPermissionDenied,
      );
      expect(service.hasScheduled('task_1', 120), isFalse);
    });

    test('shouldFailWithPluginException=true 时返回 pluginException', () async {
      service.shouldFailWithPluginException = true;
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      final result = await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: scheduledAt,
      );

      expect(result.success, isFalse);
      expect(result.failure, ReminderScheduleFailure.pluginException);
      expect(service.hasScheduled('task_1', 120), isFalse);
    });

    test('过去时间返回 pastTime 且不记录', () async {
      final pastTime = DateTime.now().subtract(const Duration(hours: 1));
      final result = await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: pastTime,
      );

      expect(result.success, isFalse);
      expect(result.failure, ReminderScheduleFailure.pastTime);
      expect(service.hasScheduled('task_1', 120), isFalse);
    });

    test('精确提醒权限未授予时返回 exactAlarmPermissionDenied 且不静默降级', () async {
      service.revokeExactAlarms();
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      final result = await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: scheduledAt,
      );

      expect(result.success, isFalse);
      expect(
        result.failure,
        ReminderScheduleFailure.exactAlarmPermissionDenied,
      );
      expect(service.hasScheduled('task_1', 120), isFalse);
    });

    test('unsupportedPlatform=true 时返回 unsupportedPlatform', () async {
      service.unsupportedPlatform = true;
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      final result = await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: scheduledAt,
      );

      expect(result.success, isFalse);
      expect(result.failure, ReminderScheduleFailure.unsupportedPlatform);
      expect(service.hasScheduled('task_1', 120), isFalse);
    });

    test('稳定通知 ID — 同一 (taskId, offsetMinutes) 多次调度返回相同 ID', () async {
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      final r1 = await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: scheduledAt,
      );
      // 先取消(模拟更新流程)
      await service.cancelReminder('task_1', 120);
      final r2 = await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: scheduledAt,
      );

      expect(r1.notificationId, r2.notificationId);
    });

    test('不同 offsetMinutes 生成不同通知 ID', () async {
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      final r1 = await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: scheduledAt,
      );
      final r2 = await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 1440,
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: scheduledAt,
      );

      expect(r1.notificationId, isNot(r2.notificationId));
    });
  });

  group('FakeNotificationReminderService - cancelReminder', () {
    test('移除 scheduled map 中的记录', () async {
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: scheduledAt,
      );
      expect(service.hasScheduled('task_1', 120), isTrue);

      await service.cancelReminder('task_1', 120);

      expect(service.hasScheduled('task_1', 120), isFalse);
      expect(service.calls, contains('cancelReminder:task_1:120'));
    });

    test('仅取消指定偏移的提醒,不影响同任务的其他提醒', () async {
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: '待办提醒',
        body: '2小时前',
        scheduledAt: scheduledAt,
      );
      await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 1440,
        title: '待办提醒',
        body: '1天前',
        scheduledAt: scheduledAt,
      );

      await service.cancelReminder('task_1', 120);

      expect(service.hasScheduled('task_1', 120), isFalse);
      expect(service.hasScheduled('task_1', 1440), isTrue);
    });
  });

  group('FakeNotificationReminderService - updateReminder', () {
    test('更新已有记录的 title/body/scheduledAt,保留同一通知 ID', () async {
      final initialTime = DateTime.now().add(const Duration(hours: 1));
      final updatedTime = DateTime.now().add(const Duration(hours: 2));
      final r1 = await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: '原标题',
        body: '原正文',
        scheduledAt: initialTime,
      );

      final r2 = await service.updateReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: '新标题',
        body: '新正文',
        scheduledAt: updatedTime,
      );

      expect(r2.success, isTrue);
      expect(r2.notificationId, r1.notificationId); // 同一稳定 ID
      final record = service.scheduled[const ReminderKey('task_1', 120)]!;
      expect(record.title, '新标题');
      expect(record.body, '新正文');
      expect(record.scheduledAt, updatedTime);
      expect(service.calls, contains('updateReminder:task_1:120'));
    });
  });

  group('FakeNotificationReminderService - cancelAllForTask', () {
    test('移除该任务的所有提醒', () async {
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: '待办提醒',
        body: '2h',
        scheduledAt: scheduledAt,
      );
      await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 1440,
        title: '待办提醒',
        body: '1d',
        scheduledAt: scheduledAt,
      );
      expect(service.hasScheduledForTask('task_1'), isTrue);

      await service.cancelAllForTask('task_1');

      expect(service.hasScheduledForTask('task_1'), isFalse);
      expect(service.scheduledCount, 0);
      expect(service.calls, contains('cancelAllForTask:task_1'));
    });
  });

  group('FakeNotificationReminderService - restoreReminders', () {
    test('权限已授予 + 精确提醒已授予时恢复未过期任务', () async {
      service.grantPermission();
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      final entries = [
        ReminderEntry(
          taskId: 'task_1',
          offsetMinutes: 120,
          title: '待办提醒',
          body: '即将截止',
          scheduledAt: scheduledAt,
          taskCompleted: false,
          taskDeleted: false,
        ),
      ];

      final restored = await service.restoreReminders(entries);

      expect(restored, 1);
      expect(service.hasScheduled('task_1', 120), isTrue);
    });

    test('已完成的任务不恢复', () async {
      service.grantPermission();
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      final entries = [
        ReminderEntry(
          taskId: 'task_1',
          offsetMinutes: 120,
          title: '待办提醒',
          body: '即将截止',
          scheduledAt: scheduledAt,
          taskCompleted: true, // 已完成
          taskDeleted: false,
        ),
      ];

      final restored = await service.restoreReminders(entries);

      expect(restored, 0);
      expect(service.hasScheduled('task_1', 120), isFalse);
    });

    test('已删除的任务不恢复', () async {
      service.grantPermission();
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      final entries = [
        ReminderEntry(
          taskId: 'task_1',
          offsetMinutes: 120,
          title: '待办提醒',
          body: '即将截止',
          scheduledAt: scheduledAt,
          taskCompleted: false,
          taskDeleted: true, // 已删除
        ),
      ];

      final restored = await service.restoreReminders(entries);

      expect(restored, 0);
      expect(service.hasScheduled('task_1', 120), isFalse);
    });

    test('已过期任务不恢复', () async {
      service.grantPermission();
      final pastTime = DateTime.now().subtract(const Duration(hours: 1));
      final entries = [
        ReminderEntry(
          taskId: 'task_1',
          offsetMinutes: 120,
          title: '待办提醒',
          body: '已过期',
          scheduledAt: pastTime,
          taskCompleted: false,
          taskDeleted: false,
        ),
      ];

      final restored = await service.restoreReminders(entries);

      expect(restored, 0);
      expect(service.hasScheduled('task_1', 120), isFalse);
    });

    test('同一 (taskId, offsetMinutes) 不重复创建(去重)', () async {
      service.grantPermission();
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      final entries = [
        ReminderEntry(
          taskId: 'task_1',
          offsetMinutes: 120,
          title: '待办提醒',
          body: '即将截止',
          scheduledAt: scheduledAt,
          taskCompleted: false,
          taskDeleted: false,
        ),
      ];

      await service.restoreReminders(entries);
      final restored2 = await service.restoreReminders(entries);

      expect(restored2, 0); // 已存在,不重复创建
      expect(service.scheduledCount, 1);
    });

    test('精确提醒权限未授予时不恢复(不假装成功)', () async {
      service.grantPermission();
      service.revokeExactAlarms();
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      final entries = [
        ReminderEntry(
          taskId: 'task_1',
          offsetMinutes: 120,
          title: '待办提醒',
          body: '即将截止',
          scheduledAt: scheduledAt,
          taskCompleted: false,
          taskDeleted: false,
        ),
      ];

      final restored = await service.restoreReminders(entries);

      expect(restored, 0);
      expect(service.hasScheduled('task_1', 120), isFalse);
    });

    test('通知权限未授予时不恢复', () async {
      service.denyPermission();
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      final entries = [
        ReminderEntry(
          taskId: 'task_1',
          offsetMinutes: 120,
          title: '待办提醒',
          body: '即将截止',
          scheduledAt: scheduledAt,
          taskCompleted: false,
          taskDeleted: false,
        ),
      ];

      final restored = await service.restoreReminders(entries);

      expect(restored, 0);
      expect(service.hasScheduled('task_1', 120), isFalse);
    });

    test('空列表返回 0', () async {
      service.grantPermission();
      final restored = await service.restoreReminders(const []);
      expect(restored, 0);
    });
  });

  group('FakeNotificationReminderService - capabilityStatus', () {
    test('默认返回 supported', () {
      expect(service.capabilityStatus(), ReminderCapabilityStatus.supported);
    });

    test('可修改为 degraded', () {
      service.capability = ReminderCapabilityStatus.degraded;
      expect(service.capabilityStatus(), ReminderCapabilityStatus.degraded);
    });
  });

  group('FakeNotificationReminderService - permissionStatus', () {
    test('初始为 notDetermined', () {
      expect(
        service.permissionStatus(),
        ReminderPermissionStatus.notDetermined,
      );
    });

    test('grantPermission 后为 granted', () {
      service.grantPermission();
      expect(service.permissionStatus(), ReminderPermissionStatus.granted);
    });

    test('denyPermission 后为 denied', () {
      service.denyPermission();
      expect(service.permissionStatus(), ReminderPermissionStatus.denied);
    });

    test('setPermission 可显式设置任意状态(模拟权限被撤销)', () {
      service.grantPermission();
      expect(service.permissionStatus(), ReminderPermissionStatus.granted);
      service.setPermission(ReminderPermissionStatus.denied);
      expect(service.permissionStatus(), ReminderPermissionStatus.denied);
    });
  });

  group('FakeNotificationReminderService - 设置入口', () {
    test('openExactAlarmSettings 被调用后记录', () async {
      await service.openExactAlarmSettings();
      expect(service.exactAlarmsSettingsOpened, isTrue);
      expect(service.calls, contains('openExactAlarmSettings'));
    });

    test('openNotificationSettings 被调用后记录', () async {
      await service.openNotificationSettings();
      expect(service.notificationSettingsOpened, isTrue);
      expect(service.calls, contains('openNotificationSettings'));
    });

    test('refreshPermissionStatus 调用计数', () async {
      await service.refreshPermissionStatus();
      await service.refreshPermissionStatus();
      expect(service.refreshCount, 2);
    });
  });

  group('FakeNotificationReminderService - reset', () {
    test('清空所有调用记录与调度记录', () async {
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: scheduledAt,
      );
      await service.requestPermission();

      expect(service.scheduled, isNotEmpty);
      expect(service.calls, isNotEmpty);

      service.reset();

      expect(service.scheduled, isEmpty);
      expect(service.calls, isEmpty);
    });

    test('reset 不影响已设置的权限状态', () {
      service.grantPermission();
      service.reset();

      expect(service.permissionStatus(), ReminderPermissionStatus.granted);
    });
  });

  group('FakeNotificationReminderService - hasScheduled', () {
    test('调度后返回 true', () async {
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: scheduledAt,
      );

      expect(service.hasScheduled('task_1', 120), isTrue);
      expect(service.hasScheduled('task_1', 1440), isFalse);
    });

    test('未调度时返回 false', () {
      expect(service.hasScheduled('task_1', 120), isFalse);
      expect(service.hasScheduledForTask('task_1'), isFalse);
    });
  });
}
