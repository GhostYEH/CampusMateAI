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
    });

    test('denyPermission() 后 requestPermission 返回 false', () async {
      service.denyPermission();
      final result = await service.requestPermission();
      expect(result, isFalse);
    });

    test('默认未授权状态(notDetermined)requestPermission 返回 true', () async {
      // notDetermined 视为"可请求",返回 true
      final result = await service.requestPermission();
      expect(result, isTrue);
    });
  });

  group('FakeNotificationReminderService - scheduleReminder', () {
    test('记录调用到 scheduled map 并返回 true', () async {
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      final result = await service.scheduleReminder(
        taskId: 'task_1',
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: scheduledAt,
      );

      expect(result, isTrue);
      expect(service.scheduled['task_1'], isNotNull);
      expect(service.scheduled['task_1']!.title, '待办提醒');
      expect(service.scheduled['task_1']!.body, '即将截止');
      expect(service.scheduled['task_1']!.scheduledAt, scheduledAt);
      expect(service.calls, contains('scheduleReminder:task_1'));
    });

    test('已拒绝权限时 scheduleReminder 返回 false 且不记录', () async {
      service.denyPermission();
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      final result = await service.scheduleReminder(
        taskId: 'task_1',
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: scheduledAt,
      );

      expect(result, isFalse);
      expect(service.scheduled['task_1'], isNull);
    });

    test('shouldFailScheduling=true 时返回 false', () async {
      service.shouldFailScheduling = true;
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      final result = await service.scheduleReminder(
        taskId: 'task_1',
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: scheduledAt,
      );

      expect(result, isFalse);
      expect(service.scheduled['task_1'], isNull);
    });

    test('过去时间 scheduleReminder 返回 false', () async {
      final pastTime = DateTime.now().subtract(const Duration(hours: 1));
      final result = await service.scheduleReminder(
        taskId: 'task_1',
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: pastTime,
      );

      expect(result, isFalse);
      expect(service.scheduled['task_1'], isNull);
    });
  });

  group('FakeNotificationReminderService - cancelReminder', () {
    test('移除 scheduled map 中的记录', () async {
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      await service.scheduleReminder(
        taskId: 'task_1',
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: scheduledAt,
      );
      expect(service.scheduled.containsKey('task_1'), isTrue);

      await service.cancelReminder('task_1');

      expect(service.scheduled.containsKey('task_1'), isFalse);
      expect(service.calls, contains('cancelReminder:task_1'));
    });
  });

  group('FakeNotificationReminderService - updateReminder', () {
    test('更新已有记录的 title/body/scheduledAt', () async {
      final initialTime = DateTime.now().add(const Duration(hours: 1));
      final updatedTime = DateTime.now().add(const Duration(hours: 2));
      await service.scheduleReminder(
        taskId: 'task_1',
        title: '原标题',
        body: '原正文',
        scheduledAt: initialTime,
      );

      final result = await service.updateReminder(
        taskId: 'task_1',
        title: '新标题',
        body: '新正文',
        scheduledAt: updatedTime,
      );

      expect(result, isTrue);
      expect(service.scheduled['task_1']!.title, '新标题');
      expect(service.scheduled['task_1']!.body, '新正文');
      expect(service.scheduled['task_1']!.scheduledAt, updatedTime);
      expect(service.calls, contains('updateReminder:task_1'));
    });
  });

  group('FakeNotificationReminderService - cancelAllForTask', () {
    test('移除 scheduled map 中的记录', () async {
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      await service.scheduleReminder(
        taskId: 'task_1',
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: scheduledAt,
      );
      expect(service.scheduled.containsKey('task_1'), isTrue);

      await service.cancelAllForTask('task_1');

      expect(service.scheduled.containsKey('task_1'), isFalse);
      expect(service.calls, contains('cancelAllForTask:task_1'));
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
  });

  group('FakeNotificationReminderService - reset', () {
    test('清空所有调用记录与调度记录', () async {
      final scheduledAt = DateTime.now().add(const Duration(hours: 1));
      await service.scheduleReminder(
        taskId: 'task_1',
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
        title: '待办提醒',
        body: '即将截止',
        scheduledAt: scheduledAt,
      );

      expect(service.hasScheduled('task_1'), isTrue);
    });

    test('未调度时返回 false', () {
      expect(service.hasScheduled('task_1'), isFalse);
    });
  });
}
