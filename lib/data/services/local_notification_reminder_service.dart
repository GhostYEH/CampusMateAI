import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest_all.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

import 'service_interfaces.dart';

/// 基于 `flutter_local_notifications` 的本地提醒实现。
///
/// 设计要点:
/// - **Android 优先**: 使用 `AndroidScheduleMode.inexactAllowWhileIdle`
///   - Android 13+ 需运行时请求 POST_NOTIFICATIONS 权限
///   - Android 12+ 需 `SCHEDULE_EXACT_ALARM` 权限(已在 AndroidManifest 声明)
/// - **时区**: 使用 `timezone` 包,在 [ensureInitialized] 中初始化
/// - **重启恢复**: Android 重启后系统会自动重新调度未来到期的 zonedSchedule
/// - **Web 降级**: Web 不支持系统通知调度,降级为应用内提醒
/// - **权限礼貌**: 已 granted 时不再弹窗;已 denied 时不再自动请求
///
/// **不直接在页面调用此实现** — 通过 [notificationReminderProvider] 注入抽象接口。
class LocalNotificationReminderService implements NotificationReminderService {
  LocalNotificationReminderService({FlutterLocalNotificationsPlugin? plugin})
      : _plugin = plugin ?? FlutterLocalNotificationsPlugin();

  final FlutterLocalNotificationsPlugin _plugin;

  /// 通知通道 ID(单通道够用)
  static const String _channelId = 'campus_mate_reminders';
  static const String _channelName = '任务提醒';
  static const String _channelDesc = '校园通知待办的截止时间提醒';

  /// 是否已初始化(_plugin 是惰性单例,首次调用方法时初始化)
  bool _initialized = false;
  bool _tzInitialized = false;

  /// 缓存权限状态(避免重复请求)
  ReminderPermissionStatus _cachedPermission =
      ReminderPermissionStatus.notDetermined;

  /// 通知 ID: 同一 taskId 始终使用相同 id,便于取消。
  /// 通过 taskId 哈希生成稳定 id(0..999999,32-bit 安全)。
  int _notificationIdFor(String taskId) {
    var hash = 0;
    for (final c in taskId.codeUnits) {
      hash = (hash * 31 + c) & 0x7fffffff;
    }
    return hash % 1000000;
  }

  /// 初始化插件与 timezone 数据库(幂等)。
  ///
  /// 由 [ReminderBootstrap] 在 main 中调用一次,或首次调度时惰性初始化。
  Future<void> ensureInitialized() async {
    if (_initialized) return;
    if (!_tzInitialized) {
      try {
        tz_data.initializeTimeZones();
        // 尝试设置本地时区(若失败则使用 UTC,后续 zonedSchedule 仍可工作)
        try {
          final localName = DateTime.now().timeZoneName;
          if (localName.isNotEmpty) {
            tz.setLocalLocation(tz.getLocation(localName));
          }
        } catch (_) {
          // 忽略: 使用默认 local
        }
        _tzInitialized = true;
      } catch (_) {
        // timezone 初始化失败,降级为不支持
        _cachedPermission = ReminderPermissionStatus.unsupported;
        return;
      }
    }
    const initSettings = InitializationSettings(
      android: AndroidInitializationSettings('@mipmap/ic_launcher'),
      iOS: DarwinInitializationSettings(
        requestAlertPermission: false,
        requestBadgePermission: false,
        requestSoundPermission: false,
      ),
    );
    try {
      await _plugin.initialize(initSettings);
      _initialized = true;
    } catch (_) {
      _cachedPermission = ReminderPermissionStatus.unsupported;
    }
  }

  @override
  Future<bool> requestPermission() async {
    if (kIsWeb) {
      _cachedPermission = ReminderPermissionStatus.unsupported;
      return false;
    }
    await ensureInitialized();
    if (_cachedPermission == ReminderPermissionStatus.granted) return true;
    if (_cachedPermission == ReminderPermissionStatus.denied) return false;

    try {
      if (Platform.isIOS) {
        final result = await _plugin
            .resolvePlatformSpecificImplementation<
                IOSFlutterLocalNotificationsPlugin>()
            ?.requestPermissions(alert: true, badge: true, sound: true);
        final granted = result ?? false;
        _cachedPermission = granted
            ? ReminderPermissionStatus.granted
            : ReminderPermissionStatus.denied;
        return granted;
      }
      if (Platform.isAndroid) {
        final android = _plugin.resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>();
        // Android 13+ 需运行时权限
        final granted =
            await android?.requestNotificationsPermission() ?? false;
        // 同时请求精确闹钟权限(用于 zonedSchedule)
        await android?.requestExactAlarmsPermission();
        _cachedPermission = granted
            ? ReminderPermissionStatus.granted
            : ReminderPermissionStatus.denied;
        return granted;
      }
    } catch (_) {
      _cachedPermission = ReminderPermissionStatus.unsupported;
      return false;
    }
    _cachedPermission = ReminderPermissionStatus.unsupported;
    return false;
  }

  @override
  Future<bool> scheduleReminder({
    required String taskId,
    required String title,
    required String body,
    required DateTime scheduledAt,
  }) async {
    if (kIsWeb) return false; // Web 不支持系统调度
    if (_cachedPermission != ReminderPermissionStatus.granted) {
      final ok = await requestPermission();
      if (!ok) return false;
    }
    // 时间已过的提醒不调度
    final now = DateTime.now();
    if (!scheduledAt.isAfter(now)) return false;

    await ensureInitialized();
    final id = _notificationIdFor(taskId);
    const androidDetails = AndroidNotificationDetails(
      _channelId,
      _channelName,
      channelDescription: _channelDesc,
      importance: Importance.high,
      priority: Priority.high,
      icon: '@mipmap/ic_launcher',
    );
    const iosDetails = DarwinNotificationDetails();
    const details = NotificationDetails(
      android: androidDetails,
      iOS: iosDetails,
    );

    try {
      // 使用 zonedSchedule 以支持时区与重启后恢复
      // `androidScheduleMode: inexactAllowWhileIdle`:
      //   - 设备低功耗时也能触发
      //   - 允许系统批处理,降低耗电
      //   - Android 重启后系统会自动重新调度未来到期的任务
      await _plugin.zonedSchedule(
        id,
        title,
        body,
        tz.TZDateTime.from(scheduledAt, tz.local),
        details,
        androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
        uiLocalNotificationDateInterpretation:
            UILocalNotificationDateInterpretation.absoluteTime,
        payload: taskId,
      );
      return true;
    } catch (_) {
      return false;
    }
  }

  @override
  Future<void> cancelReminder(String taskId) async {
    if (kIsWeb) return;
    await ensureInitialized();
    final id = _notificationIdFor(taskId);
    try {
      await _plugin.cancel(id);
    } catch (_) {
      // 忽略取消失败(可能从未调度)
    }
  }

  @override
  Future<bool> updateReminder({
    required String taskId,
    required String title,
    required String body,
    required DateTime scheduledAt,
  }) async {
    await cancelReminder(taskId);
    return scheduleReminder(
      taskId: taskId,
      title: title,
      body: body,
      scheduledAt: scheduledAt,
    );
  }

  @override
  Future<void> cancelAllForTask(String taskId) async {
    // 当前实现一任务一提醒,等同于 cancelReminder
    await cancelReminder(taskId);
  }

  @override
  ReminderCapabilityStatus capabilityStatus() {
    if (kIsWeb) return ReminderCapabilityStatus.degraded;
    if (Platform.isAndroid || Platform.isIOS) {
      return ReminderCapabilityStatus.supported;
    }
    return ReminderCapabilityStatus.degraded;
  }

  @override
  ReminderPermissionStatus permissionStatus() => _cachedPermission;
}

/// 应用启动时调用的初始化帮助函数。
///
/// 在 `main()` 中调用:
/// ```dart
/// await ReminderBootstrap.initialize();
/// ```
///
/// 失败不会抛异常,只记录日志(由调用方决定是否继续)。
class ReminderBootstrap {
  ReminderBootstrap._();

  /// 全局单例(由 main 注入,供 Provider 读取)
  static LocalNotificationReminderService? _instance;

  static LocalNotificationReminderService get instance {
    _instance ??= LocalNotificationReminderService();
    return _instance!;
  }

  /// 在 main 中调用以初始化 timezone 与插件。
  static Future<void> initialize() async {
    try {
      await instance.ensureInitialized();
    } catch (_) {
      // 提醒功能不可用不应阻塞应用启动
    }
  }
}
