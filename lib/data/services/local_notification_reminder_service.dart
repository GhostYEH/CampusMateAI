import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_timezone/flutter_timezone.dart';
import 'package:timezone/data/latest_all.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

import 'service_interfaces.dart';

/// 基于 `flutter_local_notifications` 的本地提醒实现 — Android 精确提醒完整闭环。
///
/// 设计要点(详见 `docs/reminder_guide.md`):
///
/// - **Android 精确调度**: 使用 `AndroidScheduleMode.exactAllowWhileIdle`
///   - 仅声明 `SCHEDULE_EXACT_ALARM`(不声明 `USE_EXACT_ALARM`)
///   - 调度前必须满足: `canScheduleExactAlarms == true` && 通知权限已授予 &&
///     `scheduledAt` 在未来
///   - 精确权限被拒绝时**不**静默降级为 inexact,返回 `exactAlarmPermissionDenied`
///
/// - **时区修复**: 通过 `flutter_timezone` 获取 IANA 时区名(如 `Asia/Shanghai`),
///   设置 `tz.local`。`DateTime.now().timeZoneName` 不可靠(在 Android 上常返回
///   "CST"等缩写,无法对应 IANA 数据库),不得使用。
///
/// - **稳定 notificationId**: 由 `taskId + offsetMinutes` 组合哈希生成,
///   同一 task+offset 在多次调度中产生相同 ID,从而支持"覆盖旧提醒"和"重启后去重"。
///
/// - **重启恢复**: `flutter_local_notifications` 的 `ScheduledNotificationBootReceiver`
///   会在设备重启后自动恢复 alarms(需在 AndroidManifest 注册 + RECEIVE_BOOT_COMPLETED
///   权限)。本类的 [restoreReminders] 处理"权限重新授予"或"应用更新后 alarms 丢失"
///   的场景,通过 `pendingNotificationRequests` 去重避免重复创建。
///
/// - **Web 降级**: Web 平台不支持系统调度,所有调度方法返回 `unsupportedPlatform`,
///   UI 层展示"Web 端仅提供应用内提醒"。
///
/// - **权限礼貌**: 已 granted 时不再弹窗;已 denied 时不再自动请求;精确提醒权限
///   通过 [openExactAlarmSettings] 跳转系统设置由用户主动授予。
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

  /// notificationId 取模上限 — 32-bit 安全,避免与系统其它通知冲突。
  static const int _idModulus = 1000000;

  /// 是否已初始化(_plugin 是惰性单例,首次调用方法时初始化)
  bool _initialized = false;
  bool _tzInitialized = false;
  bool _tzLocalSet = false;

  /// 缓存权限状态(避免重复请求)
  ReminderPermissionStatus _cachedPermission =
      ReminderPermissionStatus.notDetermined;

  /// 缓存 canScheduleExactAlarms 结果(由 [refreshPermissionStatus] 刷新)
  bool _cachedCanScheduleExactAlarms = false;

  /// 跟踪每个 taskId 已调度的 notificationId 集合(用于 [cancelAllForTask])。
  /// 仅内存跟踪 — 进程重启后通过 [restoreReminders] 中的 pendingNotificationRequests
  /// 查询兜底。
  final Map<String, Set<int>> _scheduledIdsByTask = {};

  /// 由 taskId + offsetMinutes 生成稳定的 notificationId。
  ///
  /// 同一 (taskId, offsetMinutes) 组合始终产生相同 ID — 支持:
  /// - 同一提醒更新时覆盖旧提醒(zonedSchedule 同 ID 会覆盖)
  /// - 重启恢复时通过 pendingNotificationRequests 去重
  /// - 取消时按 taskId 找到所有相关 ID
  ///
  /// 不使用 Dart 默认 `Object.hashCode`(跨进程不稳定)。
  /// 使用确定性字符串哈希(FNV-1a 变体,32-bit,正数)。
  static int notificationIdFor(String taskId, int offsetMinutes) {
    // FNV-1a 32-bit hash over "taskId|offsetMinutes"
    const int fnvPrime = 0x01000193;
    int hash = 0x811C9DC5;
    void mix(int byte) {
      hash ^= byte;
      hash = (hash * fnvPrime) & 0x7fffffff;
    }

    for (final c in taskId.codeUnits) {
      mix(c);
    }
    mix(0x7C); // '|'
    // 将 offsetMinutes 拆为 4 字节(小端)
    mix(offsetMinutes & 0xFF);
    mix((offsetMinutes >> 8) & 0xFF);
    mix((offsetMinutes >> 16) & 0xFF);
    mix((offsetMinutes >> 24) & 0xFF);
    return hash % _idModulus;
  }

  /// 初始化插件与 timezone 数据库(幂等)。
  ///
  /// 由 [ReminderBootstrap] 在 main 中调用一次,或首次调度时惰性初始化。
  Future<void> ensureInitialized() async {
    if (_initialized) return;
    if (!_tzInitialized) {
      try {
        tz_data.initializeTimeZones();
        _tzInitialized = true;
      } catch (_) {
        // timezone 初始化失败,降级为不支持
        _cachedPermission = ReminderPermissionStatus.unsupported;
        return;
      }
    }
    // 使用 flutter_timezone 取得 IANA 时区名并设置 tz.local
    // DateTime.now().timeZoneName 不可靠(Android 上常返回"CST"等缩写),
    // 必须使用本插件获取 IANA 名称。
    if (!_tzLocalSet) {
      try {
        final localName = await FlutterTimezone.getLocalTimezone();
        if (localName.isNotEmpty) {
          final location = tz.getLocation(localName);
          tz.setLocalLocation(location);
          _tzLocalSet = true;
        }
      } catch (_) {
        // 取不到本地时区时,默认 local (UTC) 仍可调度,只是时间显示可能偏差。
        // 此处不阻断初始化 — 让上层通过 capabilityStatus / 调度失败感知。
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
      // 初始化后立即拉取一次权限状态,避免 capabilityStatus 返回 stale 值
      await _refreshPermissionFromSystem();
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
        // Android 13+ 需运行时权限(POST_NOTIFICATIONS)。
        // Android 12- 默认授予,此调用为 no-op。
        final granted =
            await android?.requestNotificationsPermission() ?? false;
        _cachedPermission = granted
            ? ReminderPermissionStatus.granted
            : ReminderPermissionStatus.denied;
        // 同时刷新 canScheduleExactAlarms 缓存(精确提醒权限需用户在系统设置中授予,
        // requestNotificationsPermission 不会自动请求 SCHEDULE_EXACT_ALARM)
        await _refreshCanScheduleExactAlarms(android);
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
  ReminderPermissionStatus permissionStatus() => _cachedPermission;

  @override
  Future<void> refreshPermissionStatus() async {
    if (kIsWeb) {
      _cachedPermission = ReminderPermissionStatus.unsupported;
      _cachedCanScheduleExactAlarms = false;
      return;
    }
    await ensureInitialized();
    await _refreshPermissionFromSystem();
  }

  Future<void> _refreshPermissionFromSystem() async {
    if (kIsWeb) return;
    try {
      if (Platform.isAndroid) {
        final android = _plugin.resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>();
        final enabled = await android?.areNotificationsEnabled() ?? false;
        _cachedPermission = enabled
            ? ReminderPermissionStatus.granted
            : ReminderPermissionStatus.denied;
        await _refreshCanScheduleExactAlarms(android);
      } else if (Platform.isIOS) {
        final ios = _plugin.resolvePlatformSpecificImplementation<
            IOSFlutterLocalNotificationsPlugin>();
        final result = await ios?.checkPermissions();
        final granted = result?.isEnabled ?? false;
        _cachedPermission = granted
            ? ReminderPermissionStatus.granted
            : ReminderPermissionStatus.denied;
        // iOS 不需要 SCHEDULE_EXACT_ALARM,默认可调度
        _cachedCanScheduleExactAlarms = true;
      }
    } catch (_) {
      // 保留原状态
    }
  }

  Future<void> _refreshCanScheduleExactAlarms(
    AndroidFlutterLocalNotificationsPlugin? android,
  ) async {
    try {
      // flutter_local_notifications 17.x 将方法重命名为 canScheduleExactNotifications
      // (旧名 canScheduleExactAlarms 在 17.x 已删除)
      _cachedCanScheduleExactAlarms =
          await android?.canScheduleExactNotifications() ?? false;
    } catch (_) {
      _cachedCanScheduleExactAlarms = false;
    }
  }

  @override
  Future<bool> canScheduleExactAlarms() async {
    if (kIsWeb) return false;
    await ensureInitialized();
    if (Platform.isAndroid) {
      // 每次调用都从系统读取最新值(用户可能从设置页刚授予/撤销)
      final android = _plugin.resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin>();
      await _refreshCanScheduleExactAlarms(android);
      return _cachedCanScheduleExactAlarms;
    }
    if (Platform.isIOS) {
      return true;
    }
    return false;
  }

  @override
  Future<void> openExactAlarmSettings() async {
    if (kIsWeb || !Platform.isAndroid) return;
    await ensureInitialized();
    try {
      final android = _plugin.resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin>();
      // requestExactAlarmsPermission 在 Android 12+ 上打开系统"闹钟和提醒"设置页。
      // 用户授予后返回应用,UI 调用 refreshPermissionStatus 刷新状态。
      await android?.requestExactAlarmsPermission();
    } catch (_) {
      // 忽略 — 用户可能未授予,或系统不支持
    }
  }

  @override
  Future<void> openNotificationSettings() async {
    if (kIsWeb || !Platform.isAndroid) return;
    await ensureInitialized();
    try {
      final android = _plugin.resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin>();
      // 在 Android 13+ 上重新触发系统通知权限请求。
      // 若用户已"永久拒绝",系统不会弹窗 — 此时需用户手动到系统设置开启,
      // 上层 UI 应同时显示引导文案。
      await android?.requestNotificationsPermission();
    } catch (_) {
      // 忽略
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

    // 调度前检查(按规范顺序)
    if (_cachedPermission != ReminderPermissionStatus.granted) {
      // 尝试请求一次通知权限(若是 notDetermined)
      final granted = await requestPermission();
      if (!granted) {
        return const ReminderScheduleResult.failed(
          ReminderScheduleFailure.notificationPermissionDenied,
        );
      }
    }
    if (Platform.isAndroid && !await canScheduleExactAlarms()) {
      // **不**静默降级为 inexact — 返回明确的 failure
      return const ReminderScheduleResult.failed(
        ReminderScheduleFailure.exactAlarmPermissionDenied,
      );
    }
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
      // 使用 zonedSchedule 以支持时区与重启后恢复
      // `androidScheduleMode: exactAllowWhileIdle`:
      //   - 精确触发(不批处理),要求 SCHEDULE_EXACT_ALARM
      //   - 设备 Doze 状态下也能触发
      //   - Android 重启后系统会自动重新调度未来到期的任务(配合 BootReceiver)
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
      // 跟踪已调度的 ID(用于 cancelAllForTask)
      _scheduledIdsByTask.putIfAbsent(taskId, () => <int>{}).add(id);
      return ReminderScheduleResult.success(id);
    } catch (_) {
      // 插件异常 — 不虚报成功
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
    } catch (_) {
      // 忽略取消失败(可能从未调度)
    }
    _scheduledIdsByTask[taskId]?.remove(id);
  }

  @override
  Future<void> cancelAllForTask(String taskId) async {
    if (kIsWeb) return;
    await ensureInitialized();
    // 1) 先取消内存中跟踪的 ID
    final trackedIds = _scheduledIdsByTask.remove(taskId) ?? <int>{};
    for (final id in trackedIds) {
      try {
        await _plugin.cancel(id);
      } catch (_) {
        // 忽略
      }
    }
    // 2) 查询 pendingNotificationRequests 兜底:进程重启后内存跟踪丢失,
    //    通过 payload == taskId 找到所有相关 ID 并取消
    try {
      final pending = await _plugin.pendingNotificationRequests();
      for (final p in pending) {
        if (p.payload == taskId) {
          await _plugin.cancel(p.id);
        }
      }
    } catch (_) {
      // 忽略 — best effort
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
    // 先取消该任务下所有已知的提醒(支持 offset 变化时旧 ID 与新 ID 不同的场景)
    await cancelAllForTask(taskId);
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
    await ensureInitialized();

    // 权限/能力前置检查 — 不足时直接返回 0,不假装恢复
    if (_cachedPermission != ReminderPermissionStatus.granted) return 0;
    if (Platform.isAndroid && !await canScheduleExactAlarms()) return 0;

    // 取得当前 pending 列表用于去重(按 notificationId)
    // 注意: 不能用 final,因为 try/catch 两分支都要赋值,analyzer 会报
    // "final variable can only be set once"。改用可变变量 + 默认值。
    var pendingIds = <int>{};
    try {
      final pending = await _plugin.pendingNotificationRequests();
      pendingIds = pending.map((p) => p.id).toSet();
    } catch (_) {
      // 取不到 pending 列表时,不去重 — 但仍逐个尝试调度(同 ID 会覆盖)
    }

    var restored = 0;
    final now = DateTime.now();
    for (final entry in entries) {
      // 跳过已完成 / 已删除的任务
      if (entry.taskCompleted || entry.taskDeleted) continue;
      // 跳过已过期的提醒
      if (!entry.scheduledAt.isAfter(now)) continue;

      final id = notificationIdFor(entry.taskId, entry.offsetMinutes);
      // 不重复创建已存在的提醒
      if (pendingIds.contains(id)) {
        // 但要更新内存跟踪,以便后续 cancelAllForTask 能找到它
        _scheduledIdsByTask.putIfAbsent(entry.taskId, () => <int>{}).add(id);
        continue;
      }

      final result = await scheduleReminder(
        taskId: entry.taskId,
        offsetMinutes: entry.offsetMinutes,
        title: entry.title,
        body: entry.body,
        scheduledAt: entry.scheduledAt,
      );
      if (result.success) restored++;
    }
    return restored;
  }

  @override
  ReminderCapabilityStatus capabilityStatus() {
    if (kIsWeb) return ReminderCapabilityStatus.degraded;
    if (Platform.isAndroid) {
      // Android: 通知权限被拒或精确提醒权限被撤销时,降级为 degraded
      // (本实现拒绝 inexact 降级,所以 degraded 实际等于"无法调度")
      if (_cachedPermission == ReminderPermissionStatus.denied ||
          _cachedPermission == ReminderPermissionStatus.unsupported) {
        return ReminderCapabilityStatus.degraded;
      }
      // 注意:此处不读 canScheduleExactAlarms(它是 async,不能在 sync 方法中调用)。
      // 调用方应通过 canScheduleExactAlarms() 主动检查精确提醒权限。
      // capabilityStatus 只反映"平台/通知权限"层面的能力。
      return ReminderCapabilityStatus.supported;
    }
    if (Platform.isIOS) {
      return ReminderCapabilityStatus.supported;
    }
    return ReminderCapabilityStatus.degraded;
  }
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
