import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../app/providers/app_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// 提醒权限状态横幅 — 当通知权限或精确提醒权限缺失时显示。
///
/// 对齐 AGENTS.md "Android 精确提醒完整闭环":
/// - **不**静默降级为非精确提醒
/// - **不**显示"提醒已设置"
/// - 清楚提示"尚未获得精确提醒权限"
/// - 提供打开系统"闹钟和提醒"设置的操作
///
/// 三种状态:
/// 1. [ReminderPermissionBannerType.notificationDenied]: 通知显示权限未授予
///    → 引导打开应用通知设置
/// 2. [ReminderPermissionBannerType.exactAlarmDenied]: 精确提醒权限未授予
///    → 引导打开系统"闹钟和提醒"设置
/// 3. [ReminderPermissionBannerType.webDegraded]: Web 平台不支持后台精确调度
///    → 仅显示提示,无操作入口
class ReminderPermissionBanner extends ConsumerWidget {
  const ReminderPermissionBanner({
    super.key,
    required this.type,
    this.onOpenSettings,
  });

  /// 横幅类型 — 决定显示文案与操作入口。
  final ReminderPermissionBannerType type;

  /// 点击"打开设置"回调 — 由父组件注入(便于在测试中模拟)。
  ///
  /// 若为 null,则默认通过 [notificationReminderProvider] 调用对应方法:
  /// - [ReminderPermissionBannerType.notificationDenied] → openNotificationSettings
  /// - [ReminderPermissionBannerType.exactAlarmDenied] → openExactAlarmSettings
  /// - [ReminderPermissionBannerType.webDegraded] → 无操作入口
  final Future<void> Function()? onOpenSettings;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final content = _contentFor(type);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.warningSubtle.withValues(alpha: 0.45),
        borderRadius: BorderRadius.circular(AppRadius.sm),
        border: Border.all(color: AppColors.warningSubtle, width: 0.8),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(content.icon, size: 16, color: AppColors.warning),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  content.message,
                  style: AppTypography.label.copyWith(
                    fontSize: 12,
                    color: AppColors.warning,
                  ),
                ),
                if (content.actionLabel != null) ...[
                  const SizedBox(height: 6),
                  _OpenSettingsButton(
                    label: content.actionLabel!,
                    onTap: () async {
                      if (onOpenSettings != null) {
                        await onOpenSettings!();
                        return;
                      }
                      final service = ref.read(notificationReminderProvider);
                      switch (type) {
                        case ReminderPermissionBannerType.notificationDenied:
                          await service.openNotificationSettings();
                          break;
                        case ReminderPermissionBannerType.exactAlarmDenied:
                          await service.openExactAlarmSettings();
                          break;
                        case ReminderPermissionBannerType.webDegraded:
                          // 无操作入口
                          break;
                      }
                      // 用户从系统设置返回后,主动刷新权限状态。
                      if (!context.mounted) return;
                      await ref.read(reminderStatusProvider.notifier).refresh();
                    },
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// 根据横幅类型返回文案与图标。
  ///
  /// 提醒权限被拒绝时的关键文案要求:
  /// - 不静默降级
  /// - 不显示"提醒已设置"
  /// - 清楚提示"尚未获得精确提醒权限"
  static _BannerContent _contentFor(ReminderPermissionBannerType type) {
    switch (type) {
      case ReminderPermissionBannerType.notificationDenied:
        return const _BannerContent(
          message: '尚未获得通知权限,无法设置提醒。请在系统设置中授予通知显示权限。',
          actionLabel: '前往通知设置',
          icon: Icons.notifications_off_rounded,
        );
      case ReminderPermissionBannerType.exactAlarmDenied:
        return const _BannerContent(
          message: '尚未获得精确提醒权限,请在系统设置中授予"闹钟和提醒"权限。',
          actionLabel: '前往闹钟和提醒设置',
          icon: Icons.alarm_off_rounded,
        );
      case ReminderPermissionBannerType.webDegraded:
        return const _BannerContent(
          message: 'Web 端仅提供应用内提醒,精确系统提醒请使用 Android。',
          actionLabel: null,
          icon: Icons.info_outline_rounded,
        );
    }
  }
}

/// 横幅类型。
enum ReminderPermissionBannerType {
  /// 通知显示权限未授予(POST_NOTIFICATIONS)。
  notificationDenied,

  /// 精确提醒权限未授予(SCHEDULE_EXACT_ALARM)。
  exactAlarmDenied,

  /// Web 平台不支持后台精确调度(降级模式)。
  webDegraded,
}

/// "打开设置"小按钮 — 紧凑、温和、明确。
class _OpenSettingsButton extends StatelessWidget {
  const _OpenSettingsButton({
    required this.label,
    required this.onTap,
  });

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AppRadius.xs),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: AppColors.warning,
          borderRadius: BorderRadius.circular(AppRadius.xs),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.open_in_new_rounded,
              size: 12,
              color: AppColors.onPrimary,
            ),
            const SizedBox(width: 4),
            Text(
              label,
              style: AppTypography.label.copyWith(
                fontSize: 10.5,
                color: AppColors.onPrimary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 横幅内容(消息 + 操作文案 + 图标)— 使用具名类而非 record,
/// 避免老版本 analyzer 在 record 解构时类型推断失败。
class _BannerContent {
  const _BannerContent({
    required this.message,
    required this.actionLabel,
    required this.icon,
  });

  final String message;
  final String? actionLabel;
  final IconData icon;
}
