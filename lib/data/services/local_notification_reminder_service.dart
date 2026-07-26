import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_timezone/flutter_timezone.dart';
import 'package:timezone/data/latest_all.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

import 'service_interfaces.dart';

/// 基于 `flutter_local_notifications` 的本地提醒实现(Android 精确提醒优先)。
///
/// 关键设计(对齐 AGENTS.md "Android 精确提醒完整闭环"):
///
/// - **Android 精确提醒**: 使用 `AndroidScheduleMode.exactAllowWhileIdle`,
///   **不**静默降级为 inexact。精确权限被拒时返回 `exactAlarmPermissionDenied`。
/// - **权限方案**: 仅 `SCHEDULE_EXACT_ALARM`(由 AndroidManifest 声明),
///   不声明 `USE_EXACT_ALARM`(Play Store 审核更严,且不需用户主动授予)。
/// - **稳定通知 ID**: 通过 [notificationIdFor] (FNV-1a) 基于 `taskId+offsetMinutes`
///   生成,跨进程稳定,不依赖 Dart `hashCode`。
/// - **时区**: 通过 `flutter_timezone` 取得 IANA 名称后 `tz.setLocalLocation`,
///   **不**使用 `DateTime.now().timeZoneName`(在 Android 上常返回非 IANA 缩写如 CST)。
/// - **重启恢复**: AndroidManifest 注册 `ScheduledNotificationBootReceiver`,
///   系统重启 / 应用更新后由插件恢复已调度任务;
///   应用启动时调用 [restoreReminders] 主动补齐(去重)。
/// - **Web 降级**: Web 平台 `capabilityStatus` 返回 `degraded`,
///   `scheduleReminder` 返回 `unsupportedPlatform`,**不**调用任何 Android 插件 API。
///
/// **不直接在页面调用此实现** — 通过 [notificationReminderProvider] 注入抽象接口。
class LocalNotificationReminderService implements NotificationReminderService {
  LocalNotificationReminderService({FlutterLocalNotificationsPlugin? plugin})
      : _plugin = plugin ?? FlutterLocalNotificationsPlugin();

  final FlutterLocalNotificationsPlugin _plugin;

  /// 通知通道 ID(单通道够用)。
  static const String _channelId = 'campus_mate_reminders';
  static const String _channelName = '任务提醒';
  static const String _channelDesc = '校园通知待办的截止时间提醒';

  /// 是否已初始化(_plugin 是惰性单例,首次调用方法时初始化)。
  bool _initialized = false;
  bool _tzInitialized = false;
  bool _permissionQueried = false;

  /// 缓存权限状态(避免重复请求)。
  ReminderPermissionStatus _cachedPermission =
      ReminderPermissionStatus.notDetermined;

  /// 缓存 canScheduleExactAlarms(避免每次调度都查询系统)。
  bool? _cachedCanScheduleExact;

  /// 已调度通知 ID 集合,按 taskId 分组 — 用于 cancelAllForTask 与 restoreReminders 去重。
  final Map<String, Set<int>> _scheduledIdsByTask = {};

  /// 初始化插件与 timezone 数据库(幂等)。
  ///
  /// 由 [ReminderBootstrap] 在 main 中调用一次,或首次调度时惰性初始化。
  Future<void> ensureInitialized() async {
    if (_initialized) return;
    if (!_tzInitialized) {
      tz_data.initializeTimeZones();
      await _initLocalTimezone();
      _tzInitialized = true;
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
      // 插件初始化失败 — 标记为不支持,后续调度将返回 pluginException
      _cachedPermission = ReminderPermissionStatus.unsupported;
    }
  }

  /// 通过 [FlutterTimeZone] 取得 IANA 时区名称并设置 `tz.local`。
  ///
  /// **不**使用 `DateTime.now().timeZoneName` — 在 Android 上它常返回
  /// "CST" / "PST" 等非 IANA 缩写,会被 `tz.getLocation` 拒绝导致回退到 UTC。
  Future<void> _initLocalTimezone() async {
    try {
      final name = await FlutterTimezone.getLocalTimezone();
      if (name.isEmpty) return;
      final location = tz.getLocation(name);
      tz.setLocalLocation(location);
    } catch (_) {
      // 取不到 IANA 名称时保持 tz.local 默认(UTC),zonedSchedule 仍可工作,
      // 只是时区显示可能不正确 — 不阻断初始化。
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
        _permissionQueried = true;
        return granted;
      }
      if (Platform.isAndroid) {
        final android = _plugin.resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>();
        // Android 13+ 需运行时请求 POST_NOTIFICATIONS
        final granted =
            await android?.requestNotificationsPermission() ?? false;
        // 同时请求 Android 12+ 的 SCHEDULE_EXACT_ALARM(若已声明权限且未授予,引导用户授权)
        // 失败不影响通知权限的判定 — 由 canScheduleExactAlarms 单独检查
        try {
          await android?.requestExactAlarmsPermission();
          // 请求后清空缓存,让下次 canScheduleExactAlarms 重新查询
          _cachedCanScheduleExact = null;
        } catch (_) {
          // 部分平台版本不支持 — 忽略,由 canScheduleExactAlarms 兜底
        }
        _cachedPermission = granted
            ? ReminderPermissionStatus.granted
            : ReminderPermissionStatus.denied;
        _permissionQueried = true;
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
  Future<void> refreshPermissionStatus() async {
    if (kIsWeb) {
      _cachedPermission = ReminderPermissionStatus.unsupported;
      _cachedCanScheduleExact = false;
      return;
    }
    await ensureInitialized();
    // 重置缓存,强制下次查询系统
    _cachedPermission = ReminderPermissionStatus.notDetermined;
    _cachedCanScheduleExact = null;
    _permissionQueried = false;
    // 主动查询一次
    await _queryPermissionStatus();
    await canScheduleExactAlarms();
  }

  Future<void> _queryPermissionStatus() async {
    if (_permissionQueried &&
        _cachedPermission != ReminderPermissionStatus.notDetermined) {
      return;
    }
    try {
      if (Platform.isAndroid) {
        final android = _plugin.resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>();
        // 显式标注 bool?/bool:避免 `await android?.areNotificationsEnabled() ?? false`
        // 被解析为 `await (android?.areNotificationsEnabled() ?? false)`,导致最终类型为 bool?。
        final bool? result = await android?.areNotificationsEnabled();
        final bool granted = result ?? false;
        _cachedPermission = granted
            ? ReminderPermissionStatus.granted
            : ReminderPermissionStatus.denied;
      } else if (Platform.isIOS) {
        final ios = _plugin.resolvePlatformSpecificImplementation<
            IOSFlutterLocalNotificationsPlugin>();
        // flutter_local_notifications 17.x: checkPermissions() 返回
        // NotificationsEnabledOptions?(包含 isEnabled/isAlertEnabled 等字段)而非 bool?。
        final options = await ios?.checkPermissions();
        final granted = options?.isEnabled ?? false;
        _cachedPermission = granted
            ? ReminderPermissionStatus.granted
            : ReminderPermissionStatus.denied;
      }
      _permissionQueried = true;
    } catch (_) {
      _cachedPermission = ReminderPermissionStatus.unsupported;
    }
  }

  @override
  ReminderPermissionStatus permissionStatus() => _cachedPermission;

  @override
  Future<bool> canScheduleExactAlarms() async {
    if (kIsWeb) return false;
    if (!Platform.isAndroid) return true; // iOS 无此概念
    if (_cachedCanScheduleExact != null) return _cachedCanScheduleExact!;
    await ensureInitialized();
    try {
      final android = _plugin.resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin>();
      // flutter_local_notifications 17.x API: canScheduleExactNotifications
      final can = await android?.canScheduleExactNotifications() ?? false;
      _cachedCanScheduleExact = can;
      return can;
    } catch (_) {
      _cachedCanScheduleExact = false;
      return false;
    }
  }

  @override
  Future<void> openExactAlarmSettings() async {
    if (kIsWeb || !Platform.isAndroid) return;
    try {
      final android = _plugin.resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin>();
      // 打开 Android 12+ 的"闹钟和提醒"设置页
      await android?.requestExactAlarmsPermission();
    } catch (_) {
      // 用户需手动前往设置 — 不阻断流程
    }
  }

  @override
  Future<void> openNotificationSettings() async {
    // flutter_local_notifications 17.x 未提供直接打开应用通知设置页的 API。
    // Android 上若需引导用户前往通知设置,可使用 url_launcher 或 platform channel
    // 打开 `android.settings.APP_NOTIFICATION_SETTINGS` Intent(本轮不引入新依赖)。
    // 当前实现为 no-op: UI 层通过 [openExactAlarmSettings] 引导打开"闹钟和提醒",
    // 通知显示权限由 [requestPermission] 触发系统弹窗。
    if (kIsWeb || !Platform.isAndroid) return;
    try {
      // 重新触发权限弹窗(若用户已拒绝,部分系统版本会引导前往设置页)
      final android = _plugin.resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin>();
      await android?.requestNotificationsPermission();
    } catch (_) {
      // 部分平台版本不支持 — 忽略
    }
  }

  @override
  Future<ReminderScheduleResult> scheduleReminder({
    required String taskId,
    required int offsetMinutes,
    required String title,
    required String body,
    required DateTime scheduledAt,
  }) async {
    if (kIsWeb) {
      return const ReminderScheduleResult.failed(
        ReminderScheduleFailure.unsupportedPlatform,
      );
    }
    await ensureInitialized();

    // 1. 通知权限检查(若 notDetermined,尝试请求一次)
    if (_cachedPermission != ReminderPermissionStatus.granted) {
      final granted = await requestPermission();
      if (!granted) {
        return const ReminderScheduleResult.failed(
          ReminderScheduleFailure.notificationPermissionDenied,
        );
      }
    }
    // 2. 精确提醒权限检查(Android 12+)— **不**静默降级
    if (Platform.isAndroid && !await canScheduleExactAlarms()) {
      return const ReminderScheduleResult.failed(
        ReminderScheduleFailure.exactAlarmPermissionDenied,
      );
    }
    // 3. 时间必须在未来
    final now = DateTime.now();
    if (!scheduledAt.isAfter(now)) {
      return const ReminderScheduleResult.failed(
        ReminderScheduleFailure.pastTime,
      );
    }

    final id = notificationIdFor(taskId, offsetMinutes);
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
      // 使用 zonedSchedule 以支持时区与重启后恢复。
      // **exactAllowWhileIdle**: 精确触发 + 设备 idle 也能弹出。
      // 系统重启后由 ScheduledNotificationBootReceiver 自动重新调度未到期任务。
      await _plugin.zonedSchedule(
        id,
        title,
        body,
        tz.TZDateTime.from(scheduledAt, tz.local),
        details,
        androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
        uiLocalNotificationDateInterpretation:
            UILocalNotificationDateInterpretation.absoluteTime,
        payload: taskId,
      );
      _scheduledIdsByTask.putIfAbsent(taskId, () => <int>{}).add(id);
      return ReminderScheduleResult.success(id);
    } catch (_) {
      return const ReminderScheduleResult.failed(
        ReminderScheduleFailure.pluginException,
      );
    }
  }

  @override
  Future<void> cancelReminder(String taskId, int offsetMinutes) async {
    if (kIsWeb) return;
    await ensureInitialized();
    final id = notificationIdFor(taskId, offsetMinutes);
    try {
      await _plugin.cancel(id);
      _scheduledIdsByTask[taskId]?.remove(id);
      if (_scheduledIdsByTask[taskId]?.isEmpty ?? false) {
        _scheduledIdsByTask.remove(taskId);
      }
    } catch (_) {
      // 忽略取消失败(可能从未调度)
    }
  }

  @override
  Future<void> cancelAllForTask(String taskId) async {
    if (kIsWeb) return;
    await ensureInitialized();
    final ids = _scheduledIdsByTask.remove(taskId) ?? const <int>{};
    for (final id in ids) {
      try {
        await _plugin.cancel(id);
      } catch (_) {
        // 忽略单个取消失败
      }
    }
  }

  @override
  Future<ReminderScheduleResult> updateReminder({
    required String taskId,
    required int offsetMinutes,
    required String title,
    required String body,
    required DateTime scheduledAt,
  }) async {
    // 取消旧的(若存在)— 同一 (taskId, offsetMinutes) 通知 ID 相同,会被 zonedSchedule 覆盖,
    // 但显式 cancel 让 _scheduledIdsByTask 状态保持准确。
    await cancelReminder(taskId, offsetMinutes);
    return scheduleReminder(
      taskId: taskId,
      offsetMinutes: offsetMinutes,
      title: title,
      body: body,
      scheduledAt: scheduledAt,
    );
  }

  @override
  Future<int> restoreReminders(List<ReminderEntry> entries) async {
    if (kIsWeb) return 0;
    if (entries.isEmpty) return 0;
    await ensureInitialized();

    // 精确权限未授予时不恢复(避免假装成功)
    if (Platform.isAndroid && !await canScheduleExactAlarms()) return 0;
    if (_cachedPermission != ReminderPermissionStatus.granted) {
      await _queryPermissionStatus();
      if (_cachedPermission != ReminderPermissionStatus.granted) return 0;
    }

    var restored = 0;
    final now = DateTime.now();
    for (final entry in entries) {
      // 已完成 / 已删除 / 已过期的不恢复
      if (entry.taskCompleted || entry.taskDeleted) continue;
      if (!entry.scheduledAt.isAfter(now)) continue;

      final id = notificationIdFor(entry.taskId, entry.offsetMinutes);
      // 去重: 同一 (taskId, offsetMinutes) 已存在则跳过
      final existing = _scheduledIdsByTask[entry.taskId];
      if (existing != null && existing.contains(id)) continue;

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
        await _plugin.zonedSchedule(
          id,
          entry.title,
          entry.body,
          tz.TZDateTime.from(entry.scheduledAt, tz.local),
          details,
          androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
          uiLocalNotificationDateInterpretation:
              UILocalNotificationDateInterpretation.absoluteTime,
          payload: entry.taskId,
        );
        _scheduledIdsByTask.putIfAbsent(entry.taskId, () => <int>{}).add(id);
        restored++;
      } catch (_) {
        // 单条失败不影响其他条目
      }
    }
    return restored;
  }

  @override
  ReminderCapabilityStatus capabilityStatus() {
    if (kIsWeb) return ReminderCapabilityStatus.degraded;
    if (Platform.isAndroid || Platform.isIOS) {
      return ReminderCapabilityStatus.supported;
    }
    return ReminderCapabilityStatus.degraded;
  }

  /// 测试辅助: 当前内存中记录的已调度通知 ID(按 taskId)。
  /// 仅用于单元测试与诊断,不暴露给 UI。
  @visibleForTesting
  Map<String, Set<int>> get scheduledIdsByTask => _scheduledIdsByTask;
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

  /// 全局单例(由 main 注入,供 Provider 读取)。
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
