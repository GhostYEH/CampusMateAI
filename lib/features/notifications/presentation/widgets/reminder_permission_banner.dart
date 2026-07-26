import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../app/providers/app_providers.dart';
import '../../../../data/services/service_interfaces.dart';

/// 提醒权限状态横幅 — 根据当前平台/权限状态展示对应的引导信息与操作。
///
/// 设计遵循 frontend-design skill 与 [AppColors]:
/// - Web 平台:展示降级说明(无操作按钮)
/// - 通知权限被拒:展示解释 + "前往设置" 按钮(暖琥珀色,警示但不刺眼)
/// - 精确提醒权限未授予(Android 12+):展示解释 + "前往闹钟和提醒" 按钮
/// - 全部满足:不渲染任何内容(返回 [SizedBox.shrink])
///
/// **生命周期感知**(支持"用户返回应用后重新检查权限"):
/// - 内部使用 [WidgetsBindingObserver] 在 `resumed` 时递增
///   [reminderStatusRefreshTriggerProvider],触发 [refreshedReminderStatusProvider]
///   重新从系统读取最新权限状态
/// - 这保证了用户从系统设置返回后,横幅自动消失或更新
class ReminderPermissionBanner extends ConsumerStatefulWidget {
  const ReminderPermissionBanner({
    super.key,
    this.compact = false,
  });

  /// 紧凑模式 — 用于空间受限的卡片内部,减少内边距与图标尺寸。
  final bool compact;

  @override
  ConsumerState<ReminderPermissionBanner> createState() =>
      _ReminderPermissionBannerState();
}

class _ReminderPermissionBannerState
    extends ConsumerState<ReminderPermissionBanner>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // 用户从系统设置返回应用时,重新读取权限状态
    // (canScheduleExactAlarms / 通知权限 可能已变化)
    if (state == AppLifecycleState.resumed) {
      // 递增 trigger,触发 refreshedReminderStatusProvider 重新计算
      final trigger = ref.read(reminderStatusRefreshTriggerProvider);
      ref.read(reminderStatusRefreshTriggerProvider.notifier).state =
          trigger + 1;
    }
  }

  @override
  Widget build(BuildContext context) {
    final statusAsync = ref.watch(refreshedReminderStatusProvider);
    return statusAsync.when(
      data: (status) => _buildBanner(context, status),
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
    );
  }

  Widget _buildBanner(BuildContext context, ReminderStatusSnapshot status) {
    // 1) Web 平台降级说明
    if (status.capability == ReminderCapabilityStatus.degraded &&
        status.permission == ReminderPermissionStatus.unsupported) {
      return _Banner(
        icon: Icons.info_outline_rounded,
        color: AppColors.info,
        backgroundColor: AppColors.primarySubtle.withValues(alpha: 0.4),
        message: 'Web 端仅提供应用内提醒,精确系统提醒请使用 Android',
        compact: widget.compact,
      );
    }

    // 2) 通知权限被拒(或未确定且用户拒绝过)
    if (status.needsNotificationPermission) {
      final isDenied = status.permission == ReminderPermissionStatus.denied;
      return _Banner(
        icon: Icons.notifications_off_outlined,
        color: AppColors.warning,
        backgroundColor: AppColors.warningSubtle.withValues(alpha: 0.5),
        message:
            isDenied ? '通知权限被拒绝,无法接收提醒。请前往系统设置开启通知权限。' : '需要通知权限才能在截止前发送提醒。',
        actionLabel: '前往设置',
        onAction: () => _openNotificationSettings(),
        compact: widget.compact,
      );
    }

    // 3) 精确提醒权限未授予(Android 12+ SCHEDULE_EXACT_ALARM)
    if (status.needsExactAlarmPermission) {
      return _Banner(
        icon: Icons.alarm_off_rounded,
        color: AppColors.danger,
        backgroundColor: AppColors.dangerSubtle.withValues(alpha: 0.45),
        message: '尚未获得精确提醒权限。系统将不会在指定时间触发提醒,'
            '请前往"闹钟和提醒"设置中授予此权限。',
        actionLabel: '前往闹钟和提醒',
        onAction: () => _openExactAlarmSettings(),
        compact: widget.compact,
      );
    }

    // 4) 全部满足 — 不渲染
    return const SizedBox.shrink();
  }

  Future<void> _openNotificationSettings() async {
    final service = ref.read(notificationReminderProvider);
    await service.openNotificationSettings();
    // 用户返回后 didChangeAppLifecycleState 会自动刷新状态
    // 但若 openNotificationSettings 是 no-op(如已 granted),也主动触发一次刷新
    final trigger = ref.read(reminderStatusRefreshTriggerProvider);
    ref.read(reminderStatusRefreshTriggerProvider.notifier).state = trigger + 1;
  }

  Future<void> _openExactAlarmSettings() async {
    final service = ref.read(notificationReminderProvider);
    await service.openExactAlarmSettings();
    final trigger = ref.read(reminderStatusRefreshTriggerProvider);
    ref.read(reminderStatusRefreshTriggerProvider.notifier).state = trigger + 1;
  }
}

/// 内部横幅组件 — 统一视觉风格(图标 + 文案 + 可选操作)。
class _Banner extends StatelessWidget {
  const _Banner({
    required this.icon,
    required this.color,
    required this.backgroundColor,
    required this.message,
    this.actionLabel,
    this.onAction,
    this.compact = false,
  });

  final IconData icon;
  final Color color;
  final Color backgroundColor;
  final String message;
  final String? actionLabel;
  final VoidCallback? onAction;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final padding = compact
        ? const EdgeInsets.symmetric(horizontal: 10, vertical: 6)
        : const EdgeInsets.symmetric(horizontal: 12, vertical: 8);
    final iconSize = compact ? 14.0 : 16.0;
    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: padding,
      decoration: BoxDecoration(
        color: backgroundColor,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.4), width: 0.8),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: iconSize, color: color),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              message,
              style: AppTypography.caption.copyWith(
                fontSize: compact ? 11 : 12,
                color: AppColors.textPrimary,
                height: 1.35,
              ),
            ),
          ),
          if (actionLabel != null && onAction != null) ...[
            const SizedBox(width: 6),
            TextButton(
              onPressed: onAction,
              style: TextButton.styleFrom(
                foregroundColor: color,
                padding: const EdgeInsets.symmetric(horizontal: 8),
                minimumSize: const Size(0, 28),
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                textStyle: AppTypography.label.copyWith(
                  fontSize: compact ? 11 : 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
              child: Text(actionLabel!),
            ),
          ],
        ],
      ),
    );
  }
}

/// 调度失败反馈组件 — 根据 [ReminderScheduleResult] 显示对应的提示文案。
///
/// 用于 `_save` / `setReminder` 调用之后,根据返回结果决定 SnackBar 内容:
/// - `success`:可显示"提醒已设置"(由调用方控制)
/// - `exactAlarmPermissionDenied`:**不**显示"提醒已设置",
///   显示"尚未获得精确提醒权限,请前往系统设置"
/// - `notificationPermissionDenied`:显示"通知权限未授予,无法发送提醒"
/// - `pastTime`:显示"提醒时间已过期,将不会触发"
/// - `unsupportedPlatform`:显示"Web 端不支持系统提醒"
/// - `pluginException`:显示"提醒调度失败,请稍后重试"
///
/// 任务本身仍保存成功 — 此组件仅决定提醒部分的反馈。
class ReminderScheduleFeedback {
  ReminderScheduleFeedback._();

  /// 根据调度结果返回对应的提示文案。
  /// 返回 null 表示无提示(取消提醒 / 调度成功且调用方已自行提示)。
  static String? messageFor(ReminderScheduleResult? result) {
    if (result == null) return null; // 取消提醒,无需提示
    if (result.success) return null; // 成功,由调用方提示
    final failure = result.failure;
    if (failure == null) return null; // 防御性:理论上不会出现
    switch (failure) {
      case ReminderScheduleFailure.exactAlarmPermissionDenied:
        return '尚未获得精确提醒权限,提醒未设置。请前往"闹钟和提醒"设置中授予。';
      case ReminderScheduleFailure.notificationPermissionDenied:
        return '通知权限未授予,提醒未设置。请前往系统设置开启通知权限。';
      case ReminderScheduleFailure.pastTime:
        return '提醒时间已过期,将不会触发系统通知。';
      case ReminderScheduleFailure.unsupportedPlatform:
        return 'Web 端不支持系统提醒,仅记录任务信息。';
      case ReminderScheduleFailure.pluginException:
        return '提醒调度失败,请稍后重试。任务已保存。';
    }
  }
}
