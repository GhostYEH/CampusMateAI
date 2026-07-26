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

    test('默认未授权状态(notDetermined)requestPermission 转为 granted', () async {
      // notDetermined 视为"可请求",请求后转为 granted
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
    test('记录调用到 scheduled map 并返回 success', () async {
      service.grantPermission();
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      final result = await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: scheduledAt,
      );

      expect(result.success, isTrue);
      expect(result.notificationId, isNotNull);
      expect(service.hasScheduled('task_1', offsetMinutes: 120), isTrue);
      final rec = service.record('task_1', 120);
      expect(rec, isNotNull);
      expect(rec!.title, '待办提醒');
      expect(rec.body, '即将截止');
      expect(rec.scheduledAt, scheduledAt);
      expect(service.calls, contains('scheduleReminder:task_1:120'));
    });

    test('通知权限被拒绝时返回 notificationPermissionDenied 且不记录', () async {
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
      expect(service.hasScheduled('task_1'), isFalse);
    });

    test('精确提醒权限未授予时返回 exactAlarmPermissionDenied 且不静默降级', () async {
      service.grantPermission();
      service.setCanScheduleExactAlarms(false);
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
      expect(service.hasScheduled('task_1'), isFalse);
    });

    test('shouldFailWithPluginException=true 时返回 pluginException,不虚报成功',
        () async {
      service.grantPermission();
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
      expect(service.hasScheduled('task_1'), isFalse);
    });

    test('过去时间 scheduleReminder 返回 pastTime', () async {
      service.grantPermission();
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
      expect(service.hasScheduled('task_1'), isFalse);
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
    });
  });

  group('FakeNotificationReminderService - cancelReminder', () {
    test('按 (taskId, offsetMinutes) 移除记录', () async {
      service.grantPermission();
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: scheduledAt,
      );
      expect(service.hasScheduled('task_1', offsetMinutes: 120), isTrue);

      await service.cancelReminder('task_1', 120);

      expect(service.hasScheduled('task_1', offsetMinutes: 120), isFalse);
      expect(service.calls, contains('cancelReminder:task_1:120'));
    });

    test('仅取消指定 offset,不影响同任务下其它 offset', () async {
      service.grantPermission();
      final t = DateTime.now().add(const Duration(hours: 1));
      await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: 'A',
        body: '',
        scheduledAt: t,
      );
      await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 1440,
        title: 'B',
        body: '',
        scheduledAt: t,
      );

      await service.cancelReminder('task_1', 120);

      expect(service.hasScheduled('task_1', offsetMinutes: 120), isFalse);
      expect(service.hasScheduled('task_1', offsetMinutes: 1440), isTrue);
    });
  });

  group('FakeNotificationReminderService - updateReminder', () {
    test('更新已有记录的 title/body/scheduledAt', () async {
      service.grantPermission();
      final initialTime = DateTime.now().add(const Duration(hours: 1));
      final updatedTime = DateTime.now().add(const Duration(hours: 2));
      await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: '原标题',
        body: '原正文',
        scheduledAt: initialTime,
      );

      final result = await service.updateReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: '新标题',
        body: '新正文',
        scheduledAt: updatedTime,
      );

      expect(result.success, isTrue);
      final rec = service.record('task_1', 120);
      expect(rec!.title, '新标题');
      expect(rec.body, '新正文');
      expect(rec.scheduledAt, updatedTime);
      expect(service.calls, contains('updateReminder:task_1:120'));
    });

    test('offset 变化时取消旧 offset 并调度新 offset', () async {
      service.grantPermission();
      final t = DateTime.now().add(const Duration(hours: 1));
      await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: 'A',
        body: '',
        scheduledAt: t,
      );

      await service.updateReminder(
        taskId: 'task_1',
        offsetMinutes: 1440,
        title: 'B',
        body: '',
        scheduledAt: t,
      );

      // updateReminder 内部 cancelAllForTask 应清空 task_1 下所有 offset
      // 然后调度新 offset=1440
      expect(service.hasScheduled('task_1', offsetMinutes: 120), isFalse);
      expect(service.hasScheduled('task_1', offsetMinutes: 1440), isTrue);
    });
  });

  group('FakeNotificationReminderService - cancelAllForTask', () {
    test('移除该 taskId 下所有 offset 的记录', () async {
      service.grantPermission();
      final t = DateTime.now().add(const Duration(hours: 1));
      await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 120,
        title: 'A',
        body: '',
        scheduledAt: t,
      );
      await service.scheduleReminder(
        taskId: 'task_1',
        offsetMinutes: 1440,
        title: 'B',
        body: '',
        scheduledAt: t,
      );

      await service.cancelAllForTask('task_1');

      expect(service.recordsForTask('task_1'), isEmpty);
      expect(service.calls, contains('cancelAllForTask:task_1'));
    });
  });

  group('FakeNotificationReminderService - capabilityStatus', () {
    test('默认返回 supported', () {
      service.grantPermission();
      expect(service.capabilityStatus(), ReminderCapabilityStatus.supported);
    });

    test('可修改为 degraded', () {
      service.grantPermission();
      service.capability = ReminderCapabilityStatus.degraded;
      expect(service.capabilityStatus(), ReminderCapabilityStatus.degraded);
    });

    test('通知权限被拒时返回 degraded', () {
      service.denyPermission();
      expect(service.capabilityStatus(), ReminderCapabilityStatus.degraded);
    });

    test('unsupportedPlatform=true 时返回 degraded', () {
      service.unsupportedPlatform = true;
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

    test('setPermission 可直接设置任意状态', () {
      service.setPermission(ReminderPermissionStatus.unsupported);
      expect(service.permissionStatus(), ReminderPermissionStatus.unsupported);
    });
  });

  group('FakeNotificationReminderService - canScheduleExactAlarms', () {
    test('默认为 true', () async {
      expect(await service.canScheduleExactAlarms(), isTrue);
    });

    test('setCanScheduleExactAlarms(false) 后为 false', () async {
      service.setCanScheduleExactAlarms(false);
      expect(await service.canScheduleExactAlarms(), isFalse);
    });

    test('unsupportedPlatform=true 时为 false', () async {
      service.unsupportedPlatform = true;
      expect(await service.canScheduleExactAlarms(), isFalse);
    });
  });

  group('FakeNotificationReminderService - openSettings', () {
    test('openExactAlarmSettings 计数自增', () async {
      expect(service.openExactAlarmSettingsCalls, 0);
      await service.openExactAlarmSettings();
      expect(service.openExactAlarmSettingsCalls, 1);
    });

    test('openNotificationSettings 计数自增', () async {
      expect(service.openNotificationSettingsCalls, 0);
      await service.openNotificationSettings();
      expect(service.openNotificationSettingsCalls, 1);
    });
  });

  group('FakeNotificationReminderService - restoreReminders', () {
    test('跳过已完成 / 已删除 / 已过期的条目', () async {
      service.grantPermission();
      final future = DateTime.now().add(const Duration(hours: 1));
      final past = DateTime.now().subtract(const Duration(hours: 1));
      final entries = [
        ReminderEntry(
          taskId: 't1',
          title: 'A',
          body: '',
          scheduledAt: future,
          offsetMinutes: 120,
          taskCompleted: false,
          taskDeleted: false,
        ),
        ReminderEntry(
          taskId: 't2',
          title: 'B',
          body: '',
          scheduledAt: future,
          offsetMinutes: 120,
          taskCompleted: true,
          taskDeleted: false,
        ),
        ReminderEntry(
          taskId: 't3',
          title: 'C',
          body: '',
          scheduledAt: future,
          offsetMinutes: 120,
          taskCompleted: false,
          taskDeleted: true,
        ),
        ReminderEntry(
          taskId: 't4',
          title: 'D',
          body: '',
          scheduledAt: past,
          offsetMinutes: 120,
          taskCompleted: false,
          taskDeleted: false,
        ),
      ];

      final restored = await service.restoreReminders(entries);
      expect(restored, 1);
      expect(service.hasScheduled('t1', offsetMinutes: 120), isTrue);
      expect(service.hasScheduled('t2'), isFalse);
      expect(service.hasScheduled('t3'), isFalse);
      expect(service.hasScheduled('t4'), isFalse);
    });

    test('不重复创建已存在的提醒(通过 simulatedPendingIds 去重)', () async {
      service.grantPermission();
      final future = DateTime.now().add(const Duration(hours: 1));
      // 预先调度一条
      await service.scheduleReminder(
        taskId: 't1',
        offsetMinutes: 120,
        title: 'old',
        body: '',
        scheduledAt: future,
      );

      final restored = await service.restoreReminders([
        ReminderEntry(
          taskId: 't1',
          title: 'new',
          body: '',
          scheduledAt: future,
          offsetMinutes: 120,
          taskCompleted: false,
          taskDeleted: false,
        ),
      ]);

      // 已存在 — 不重复创建,但返回 0(没有新增)
      expect(restored, 0);
      // 记录仍是旧的(未覆盖)
      expect(service.record('t1', 120)!.title, 'old');
    });

    test('权限不足时返回 0,不假装恢复', () async {
      service.grantPermission();
      service.setCanScheduleExactAlarms(false);
      final future = DateTime.now().add(const Duration(hours: 1));
      final restored = await service.restoreReminders([
        ReminderEntry(
          taskId: 't1',
          title: 'A',
          body: '',
          scheduledAt: future,
          offsetMinutes: 120,
          taskCompleted: false,
          taskDeleted: false,
        ),
      ]);
      expect(restored, 0);
      expect(service.hasScheduled('t1'), isFalse);
    });

    test('记录调用参数到 restoreCalls', () async {
      service.grantPermission();
      final future = DateTime.now().add(const Duration(hours: 1));
      final entries = [
        ReminderEntry(
          taskId: 't1',
          title: 'A',
          body: '',
          scheduledAt: future,
          offsetMinutes: 120,
          taskCompleted: false,
          taskDeleted: false,
        ),
      ];
      await service.restoreReminders(entries);
      expect(service.restoreCalls.length, 1);
      expect(service.restoreCalls.first.length, 1);
      expect(service.restoreCalls.first.first.taskId, 't1');
    });
  });

  group('FakeNotificationReminderService - reset', () {
    test('清空所有调用记录与调度记录', () async {
      service.grantPermission();
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
      expect(service.restoreCalls, isEmpty);
      expect(service.simulatedPendingIds, isEmpty);
    });

    test('reset 不影响已设置的权限状态', () {
      service.grantPermission();
      service.reset();

      expect(service.permissionStatus(), ReminderPermissionStatus.granted);
    });
  });

  group('FakeNotificationReminderService - notificationIdFor 稳定性', () {
    test('同 (taskId, offset) 产生相同 ID', () {
      final id1 = FakeNotificationReminderService.notificationIdFor(
        'task_abc',
        120,
      );
      final id2 = FakeNotificationReminderService.notificationIdFor(
        'task_abc',
        120,
      );
      expect(id1, id2);
    });

    test('不同 offset 产生不同 ID', () {
      final id1 = FakeNotificationReminderService.notificationIdFor(
        'task_abc',
        120,
      );
      final id2 = FakeNotificationReminderService.notificationIdFor(
        'task_abc',
        1440,
      );
      expect(id1, isNot(id2));
    });

    test('不同 taskId 产生不同 ID', () {
      final id1 = FakeNotificationReminderService.notificationIdFor(
        'task_abc',
        120,
      );
      final id2 = FakeNotificationReminderService.notificationIdFor(
        'task_xyz',
        120,
      );
      expect(id1, isNot(id2));
    });

    test('ID 在 32-bit 安全范围(< 1000000)', () {
      for (final taskId in ['a', 'b', 'long_task_id_12345', '']) {
        for (final offset in [0, 1, 120, 1440, 2880, 1 << 20]) {
          final id = FakeNotificationReminderService.notificationIdFor(
            taskId,
            offset,
          );
          expect(id, lessThan(1000000));
          expect(id, greaterThanOrEqualTo(0));
        }
      }
    });
  });
}
