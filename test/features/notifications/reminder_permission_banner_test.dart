import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/data/services/service_interfaces.dart';
import 'package:campus_companion/features/notifications/presentation/widgets/reminder_permission_banner.dart';
import 'package:campus_companion/mock/mock_services/fake_notification_reminder_service.dart';

Widget _wrap(ProviderContainer container, Widget child) {
  return UncontrolledProviderScope(
    container: container,
    child: MaterialApp(
      home: Scaffold(body: Center(child: child)),
    ),
  );
}

void main() {
  group('ReminderPermissionBanner - 状态展示', () {
    testWidgets('Web 平台(degraded + unsupported)→ 显示降级文案', (tester) async {
      final fake = FakeNotificationReminderService(
        unsupportedPlatform: true,
        capability: ReminderCapabilityStatus.degraded,
        initialPermission: ReminderPermissionStatus.unsupported,
      );
      final container = ProviderContainer(
        overrides: [
          notificationReminderProvider.overrideWithValue(fake),
        ],
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        _wrap(container, const ReminderPermissionBanner()),
      );
      await tester.pumpAndSettle();

      expect(find.textContaining('Web 端仅提供应用内提醒'), findsOneWidget);
      expect(find.text('前往设置'), findsNothing);
      expect(find.text('前往闹钟和提醒'), findsNothing);
    });

    testWidgets('通知权限被拒 → 显示拒绝文案 + 前往设置按钮', (tester) async {
      final fake = FakeNotificationReminderService(
        initialPermission: ReminderPermissionStatus.denied,
        canScheduleExactAlarmsFlag: true,
      );
      final container = ProviderContainer(
        overrides: [
          notificationReminderProvider.overrideWithValue(fake),
        ],
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        _wrap(container, const ReminderPermissionBanner()),
      );
      await tester.pumpAndSettle();

      expect(find.textContaining('通知权限被拒绝'), findsOneWidget);
      expect(find.text('前往设置'), findsOneWidget);
    });

    testWidgets('通知权限已授但精确权限未授 → 显示精确权限文案 + 前往闹钟和提醒按钮', (tester) async {
      final fake = FakeNotificationReminderService(
        initialPermission: ReminderPermissionStatus.granted,
        canScheduleExactAlarmsFlag: false,
        capability: ReminderCapabilityStatus.supported,
      );
      final container = ProviderContainer(
        overrides: [
          notificationReminderProvider.overrideWithValue(fake),
        ],
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        _wrap(container, const ReminderPermissionBanner()),
      );
      await tester.pumpAndSettle();

      expect(find.textContaining('尚未获得精确提醒权限'), findsOneWidget);
      expect(find.text('前往闹钟和提醒'), findsOneWidget);
    });

    testWidgets('全部满足 → 不渲染任何内容', (tester) async {
      final fake = FakeNotificationReminderService(
        initialPermission: ReminderPermissionStatus.granted,
        canScheduleExactAlarmsFlag: true,
        capability: ReminderCapabilityStatus.supported,
      );
      final container = ProviderContainer(
        overrides: [
          notificationReminderProvider.overrideWithValue(fake),
        ],
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        _wrap(container, const ReminderPermissionBanner()),
      );
      await tester.pumpAndSettle();

      // 应该是 SizedBox.shrink — 找不到任何文本
      expect(find.byType(Text), findsNothing);
    });

    testWidgets('点击"前往闹钟和提醒" → 调用 openExactAlarmSettings', (tester) async {
      final fake = FakeNotificationReminderService(
        initialPermission: ReminderPermissionStatus.granted,
        canScheduleExactAlarmsFlag: false,
        capability: ReminderCapabilityStatus.supported,
      );
      final container = ProviderContainer(
        overrides: [
          notificationReminderProvider.overrideWithValue(fake),
        ],
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        _wrap(container, const ReminderPermissionBanner()),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('前往闹钟和提醒'));
      await tester.pumpAndSettle();

      expect(fake.openExactAlarmSettingsCalls, 1);
    });

    testWidgets('点击"前往设置" → 调用 openNotificationSettings', (tester) async {
      final fake = FakeNotificationReminderService(
        initialPermission: ReminderPermissionStatus.denied,
        canScheduleExactAlarmsFlag: true,
      );
      final container = ProviderContainer(
        overrides: [
          notificationReminderProvider.overrideWithValue(fake),
        ],
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        _wrap(container, const ReminderPermissionBanner()),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('前往设置'));
      await tester.pumpAndSettle();

      expect(fake.openNotificationSettingsCalls, 1);
    });
  });
}
