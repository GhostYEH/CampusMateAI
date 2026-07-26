import '../../data/services/service_interfaces.dart';

/// Fake 本地提醒服务 — 单元测试与 Widget 测试使用。
///
/// 不依赖 `flutter_local_notifications` 插件,记录所有调用并可控返回。
/// 在测试中通过 `ProviderScope.overrides` 注入:
///
/// ```dart
/// final fake = FakeNotificationReminderService();
/// final container = ProviderContainer(overrides: [
///   notificationReminderProvider.overrideWith((ref) => fake),
/// ]);
/// ```
///
/// 行为约定(对齐 [LocalNotificationReminderService]):
/// - 调度前检查 [permission] / [canScheduleExactAlarmsFlag] / 时间在未来
/// - 精确权限被拒时返回 `exactAlarmPermissionDenied`,**不**静默降级
/// - 通知权限被拒时返回 `notificationPermissionDenied`
/// - 时间已过时返回 `pastTime`
/// - [shouldFailWithPluginException]=true 时返回 `pluginException`
/// - [unsupportedPlatform]=true 时返回 `unsupportedPlatform`(模拟 Web)
/// - 通过 `taskId + offsetMinutes` 作为 key 存储,支持稳定 ID 去重
class FakeNotificationReminderService implements NotificationReminderService {
  FakeNotificationReminderService({
    this.capability = ReminderCapabilityStatus.supported,
    this.initialPermission = ReminderPermissionStatus.notDetermined,
    this.canScheduleExactAlarmsFlag = true,
    this.shouldFailWithPluginException = false,
    this.unsupportedPlatform = false,
  }) : _permission = initialPermission;

  /// 当前能力状态(可被测试修改)。
  ReminderCapabilityStatus capability;

  /// 初始通知权限(用于 [permissionStatus] 与 [requestPermission])。
  ///
  /// 测试中可通过 [grantPermission] / [denyPermission] / [setPermission] 修改。
  final ReminderPermissionStatus initialPermission;

  /// 是否可调度精确闹钟(对齐 Android `canScheduleExactAlarms()`)。
  bool canScheduleExactAlarmsFlag;

  /// 模拟插件调用异常(返回 `pluginException`,不虚报成功)。
  bool shouldFailWithPluginException;

  /// 模拟 Web 平台(返回 `unsupportedPlatform`)。
  bool unsupportedPlatform;

  /// 当前权限状态(由 [requestPermission] / [grantPermission] 等修改)。
  ReminderPermissionStatus _permission;

  /// 已调度的提醒: (taskId, offsetMinutes) -> record
  final Map<({String taskId, int offsetMinutes}), FakeReminderRecord>
      scheduled = {};

  /// 调用记录(便于断言)。
  final List<String> calls = [];

  /// 模拟 `pendingNotificationRequests` — restoreReminders 用此去重。
  /// 默认与 [scheduled] 同步;测试可手动修改以模拟"系统仍持有 alarm"。
  final Set<int> simulatedPendingIds = <int>{};

  /// restoreReminders 的调用记录(便于断言去重逻辑)。
  final List<List<ReminderEntry>> restoreCalls = [];

  /// openExactAlarmSettings / openNotificationSettings 调用计数。
  int openExactAlarmSettingsCalls = 0;
  int openNotificationSettingsCalls = 0;

  /// 最近一次 requestPermission 的返回值(供测试断言"已授权不重复弹窗")。
  bool? lastRequestPermissionResult;

  @override
  Future<bool> requestPermission() async {
    calls.add('requestPermission');
    if (unsupportedPlatform) {
      _permission = ReminderPermissionStatus.unsupported;
      lastRequestPermissionResult = false;
      return false;
    }
    // notDetermined 视为"可请求",请求后转为 granted
    if (_permission == ReminderPermissionStatus.notDetermined) {
      _permission = ReminderPermissionStatus.granted;
    }
    // denied / unsupported 不再自动请求,返回当前状态
    final granted = _permission == ReminderPermissionStatus.granted;
    lastRequestPermissionResult = granted;
    return granted;
  }

  @override
  ReminderPermissionStatus permissionStatus() => _permission;

  @override
  Future<void> refreshPermissionStatus() async {
    calls.add('refreshPermissionStatus');
    // 模拟从系统读取最新状态 — 测试可通过 [setPermission] 主动修改
  }

  @override
  Future<bool> canScheduleExactAlarms() async {
    calls.add('canScheduleExactAlarms');
    if (unsupportedPlatform) return false;
    return canScheduleExactAlarmsFlag;
  }

  @override
  Future<void> openExactAlarmSettings() async {
    calls.add('openExactAlarmSettings');
    openExactAlarmSettingsCalls++;
    // 测试可在此后调用 [setCanScheduleExactAlarms] 模拟用户已授予
  }

  @override
  Future<void> openNotificationSettings() async {
    calls.add('openNotificationSettings');
    openNotificationSettingsCalls++;
  }

  @override
  Future<ReminderScheduleResult> scheduleReminder({
    required String taskId,
    required int offsetMinutes,
    required String title,
    required String body,
    required DateTime scheduledAt,
  }) async {
    calls.add('scheduleReminder:$taskId:$offsetMinutes');
    if (unsupportedPlatform) {
      return const ReminderScheduleResult.failed(
        ReminderScheduleFailure.unsupportedPlatform,
      );
    }
    if (shouldFailWithPluginException) {
      return const ReminderScheduleResult.failed(
        ReminderScheduleFailure.pluginException,
      );
    }
    if (_permission == ReminderPermissionStatus.denied ||
        _permission == ReminderPermissionStatus.unsupported) {
      return const ReminderScheduleResult.failed(
        ReminderScheduleFailure.notificationPermissionDenied,
      );
    }
    if (!canScheduleExactAlarmsFlag) {
      // **不**静默降级为 inexact
      return const ReminderScheduleResult.failed(
        ReminderScheduleFailure.exactAlarmPermissionDenied,
      );
    }
    if (!scheduledAt.isAfter(DateTime.now())) {
      return const ReminderScheduleResult.failed(
        ReminderScheduleFailure.pastTime,
      );
    }
    final id = notificationIdFor(taskId, offsetMinutes);
    // 注意: record 命名字段值语法是 (name: value), 不能写成 ({name: value})
    // — 后者会被解析为 Map 字面量包在 parens 里, 与 Map<({...}), V> 的 key 类型不匹配
    scheduled[(taskId: taskId, offsetMinutes: offsetMinutes)] =
        FakeReminderRecord(
      id: id,
      title: title,
      body: body,
      scheduledAt: scheduledAt,
      offsetMinutes: offsetMinutes,
    );
    simulatedPendingIds.add(id);
    return ReminderScheduleResult.success(id);
  }

  @override
  Future<void> cancelReminder(String taskId, int offsetMinutes) async {
    calls.add('cancelReminder:$taskId:$offsetMinutes');
    final key = (taskId: taskId, offsetMinutes: offsetMinutes);
    final removed = scheduled.remove(key);
    if (removed != null) {
      simulatedPendingIds.remove(removed.id);
    }
  }

  @override
  Future<void> cancelAllForTask(String taskId) async {
    calls.add('cancelAllForTask:$taskId');
    final keysToRemove =
        scheduled.keys.where((k) => k.taskId == taskId).toList(growable: false);
    for (final key in keysToRemove) {
      final removed = scheduled.remove(key);
      if (removed != null) {
        simulatedPendingIds.remove(removed.id);
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
    calls.add('updateReminder:$taskId:$offsetMinutes');
    // 等同于 cancelAllForTask + schedule
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
    calls.add('restoreReminders:${entries.length}');
    restoreCalls.add(List<ReminderEntry>.unmodifiable(entries));

    if (unsupportedPlatform) return 0;
    if (_permission != ReminderPermissionStatus.granted) return 0;
    if (!canScheduleExactAlarmsFlag) return 0;

    var restored = 0;
    final now = DateTime.now();
    for (final entry in entries) {
      if (entry.taskCompleted || entry.taskDeleted) continue;
      if (!entry.scheduledAt.isAfter(now)) continue;

      final id = notificationIdFor(entry.taskId, entry.offsetMinutes);
      // 不重复创建已存在的提醒
      if (simulatedPendingIds.contains(id)) continue;

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
    if (unsupportedPlatform) return ReminderCapabilityStatus.degraded;
    if (_permission == ReminderPermissionStatus.denied ||
        _permission == ReminderPermissionStatus.unsupported) {
      return ReminderCapabilityStatus.degraded;
    }
    return capability;
  }

  // ====== 测试辅助方法 ======

  /// 模拟用户授予通知权限。
  void grantPermission() {
    _permission = ReminderPermissionStatus.granted;
  }

  /// 模拟用户拒绝通知权限。
  void denyPermission() {
    _permission = ReminderPermissionStatus.denied;
  }

  /// 直接设置权限状态(模拟"用户从系统设置撤销权限"等场景)。
  void setPermission(ReminderPermissionStatus status) {
    _permission = status;
  }

  /// 设置 canScheduleExactAlarms 标志(模拟用户授予/撤销精确提醒权限)。
  void setCanScheduleExactAlarms(bool value) {
    canScheduleExactAlarmsFlag = value;
  }

  /// 当前是否已调度指定 (taskId, offsetMinutes) 的提醒。
  bool hasScheduled(String taskId, {int? offsetMinutes}) {
    if (offsetMinutes == null) {
      return scheduled.keys.any((k) => k.taskId == taskId);
    }
    return scheduled
        .containsKey((taskId: taskId, offsetMinutes: offsetMinutes));
  }

  /// 取得指定 (taskId, offsetMinutes) 的记录(便于断言字段)。
  FakeReminderRecord? record(String taskId, int offsetMinutes) {
    return scheduled[(taskId: taskId, offsetMinutes: offsetMinutes)];
  }

  /// 取得指定 taskId 下的所有记录。
  List<FakeReminderRecord> recordsForTask(String taskId) {
    return scheduled.entries
        .where((e) => e.key.taskId == taskId)
        .map((e) => e.value)
        .toList(growable: false);
  }

  /// 清空所有调度记录(不影响权限状态)。
  void reset() {
    scheduled.clear();
    calls.clear();
    restoreCalls.clear();
    simulatedPendingIds.clear();
    openExactAlarmSettingsCalls = 0;
    openNotificationSettingsCalls = 0;
    lastRequestPermissionResult = null;
  }

  /// 稳定 ID 生成(与 [LocalNotificationReminderService.notificationIdFor]
  /// 完全一致的 FNV-1a 实现,便于测试断言跨进程稳定)。
  static int notificationIdFor(String taskId, int offsetMinutes) {
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
    mix(offsetMinutes & 0xFF);
    mix((offsetMinutes >> 8) & 0xFF);
    mix((offsetMinutes >> 16) & 0xFF);
    mix((offsetMinutes >> 24) & 0xFF);
    return hash % 1000000;
  }
}

/// Fake 提醒记录(测试用,公开以便测试断言读取字段)。
class FakeReminderRecord {
  const FakeReminderRecord({
    required this.id,
    required this.title,
    required this.body,
    required this.scheduledAt,
    required this.offsetMinutes,
  });

  /// 由 `taskId + offsetMinutes` 生成的稳定 notificationId。
  final int id;
  final String title;
  final String body;
  final DateTime scheduledAt;
  final int offsetMinutes;
}
