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
/// 与 [LocalNotificationReminderService] 行为对齐:
/// - 同一 (taskId, offsetMinutes) 生成稳定通知 ID(经 [notificationIdFor])
/// - 调度前检查权限 / canScheduleExactAlarms / 时间在未来
/// - 精确权限被拒时返回 `exactAlarmPermissionDenied`,**不**静默降级
/// - Web 降级([unsupportedPlatform]=true)时返回 `unsupportedPlatform`
/// - 插件异常([shouldFailWithPluginException]=true)时返回 `pluginException`
class FakeNotificationReminderService implements NotificationReminderService {
  FakeNotificationReminderService({
    this.capability = ReminderCapabilityStatus.supported,
    this.initialPermission = ReminderPermissionStatus.notDetermined,
    this.canScheduleExactAlarmsFlag = true,
    this.shouldFailWithPluginException = false,
    this.unsupportedPlatform = false,
  }) : _permission = initialPermission;

  /// 当前平台能力(默认 supported,Web 测试设为 degraded)。
  ReminderCapabilityStatus capability;

  /// 初始通知显示权限状态。
  ReminderPermissionStatus initialPermission;

  /// `canScheduleExactAlarms()` 返回值(默认 true,模拟已授予精确提醒权限)。
  bool canScheduleExactAlarmsFlag;

  /// 模拟插件调用抛异常 — 用于验证"插件异常时不虚报成功"。
  bool shouldFailWithPluginException;

  /// 模拟 Web 平台 — `scheduleReminder` 直接返回 `unsupportedPlatform`。
  bool unsupportedPlatform;

  ReminderPermissionStatus _permission;

  /// 已调度的提醒: (taskId, offsetMinutes) -> 记录。
  final Map<ReminderKey, FakeReminderRecord> scheduled = {};

  /// 调用记录(便于断言)。
  final List<String> calls = [];

  /// 已调度通知 ID(按 taskId 分组)— 与 LocalNotificationReminderService 行为一致。
  final Map<String, Set<int>> _scheduledIdsByTask = {};

  bool _permissionRequested = false;
  bool _exactAlarmsOpened = false;
  bool _notificationSettingsOpened = false;
  int _refreshCount = 0;

  @override
  Future<bool> requestPermission() async {
    calls.add('requestPermission');
    _permissionRequested = true;
    if (unsupportedPlatform) {
      _permission = ReminderPermissionStatus.unsupported;
      return false;
    }
    if (_permission == ReminderPermissionStatus.granted) return true;
    if (_permission == ReminderPermissionStatus.denied) return false;
    // notDetermined: 模拟首次请求,根据 initialPermission 决定结果
    _permission = initialPermission == ReminderPermissionStatus.denied
        ? ReminderPermissionStatus.denied
        : ReminderPermissionStatus.granted;
    return _permission == ReminderPermissionStatus.granted;
  }

  @override
  Future<void> refreshPermissionStatus() async {
    calls.add('refreshPermissionStatus');
    _refreshCount++;
    // 模拟从系统重新查询 — 不改变 _permission(测试可通过 setPermission 主动设置)
  }

  @override
  ReminderPermissionStatus permissionStatus() => _permission;

  @override
  Future<bool> canScheduleExactAlarms() async {
    calls.add('canScheduleExactAlarms');
    if (unsupportedPlatform) return false;
    return canScheduleExactAlarmsFlag;
  }

  @override
  Future<void> openExactAlarmSettings() async {
    calls.add('openExactAlarmSettings');
    _exactAlarmsOpened = true;
  }

  @override
  Future<void> openNotificationSettings() async {
    calls.add('openNotificationSettings');
    _notificationSettingsOpened = true;
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
    // 1. 通知权限
    if (_permission != ReminderPermissionStatus.granted) {
      final granted = await requestPermission();
      if (!granted) {
        return const ReminderScheduleResult.failed(
          ReminderScheduleFailure.notificationPermissionDenied,
        );
      }
    }
    // 2. 精确提醒权限(不静默降级)
    if (capability == ReminderCapabilityStatus.supported &&
        !canScheduleExactAlarmsFlag) {
      return const ReminderScheduleResult.failed(
        ReminderScheduleFailure.exactAlarmPermissionDenied,
      );
    }
    // 3. 时间必须在未来
    if (!scheduledAt.isAfter(DateTime.now())) {
      return const ReminderScheduleResult.failed(
        ReminderScheduleFailure.pastTime,
      );
    }
    // 4. 插件异常
    if (shouldFailWithPluginException) {
      return const ReminderScheduleResult.failed(
        ReminderScheduleFailure.pluginException,
      );
    }
    final id = notificationIdFor(taskId, offsetMinutes);
    final key = ReminderKey(taskId, offsetMinutes);
    scheduled[key] = FakeReminderRecord(
      notificationId: id,
      title: title,
      body: body,
      scheduledAt: scheduledAt,
    );
    _scheduledIdsByTask.putIfAbsent(taskId, () => <int>{}).add(id);
    return ReminderScheduleResult.success(id);
  }

  @override
  Future<void> cancelReminder(String taskId, int offsetMinutes) async {
    calls.add('cancelReminder:$taskId:$offsetMinutes');
    final key = ReminderKey(taskId, offsetMinutes);
    final id = notificationIdFor(taskId, offsetMinutes);
    scheduled.remove(key);
    _scheduledIdsByTask[taskId]?.remove(id);
    if (_scheduledIdsByTask[taskId]?.isEmpty ?? false) {
      _scheduledIdsByTask.remove(taskId);
    }
  }

  @override
  Future<void> cancelAllForTask(String taskId) async {
    calls.add('cancelAllForTask:$taskId');
    scheduled.removeWhere((k, _) => k.taskId == taskId);
    _scheduledIdsByTask.remove(taskId);
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
    calls.add('restoreReminders:${entries.length}');
    if (unsupportedPlatform) return 0;
    if (entries.isEmpty) return 0;
    if (_permission != ReminderPermissionStatus.granted) return 0;
    if (capability == ReminderCapabilityStatus.supported &&
        !canScheduleExactAlarmsFlag) {
      return 0;
    }
    var restored = 0;
    final now = DateTime.now();
    for (final entry in entries) {
      if (entry.taskCompleted || entry.taskDeleted) continue;
      if (!entry.scheduledAt.isAfter(now)) continue;
      final key = ReminderKey(entry.taskId, entry.offsetMinutes);
      // 去重
      if (scheduled.containsKey(key)) continue;
      final id = notificationIdFor(entry.taskId, entry.offsetMinutes);
      scheduled[key] = FakeReminderRecord(
        notificationId: id,
        title: entry.title,
        body: entry.body,
        scheduledAt: entry.scheduledAt,
      );
      _scheduledIdsByTask.putIfAbsent(entry.taskId, () => <int>{}).add(id);
      restored++;
    }
    return restored;
  }

  @override
  ReminderCapabilityStatus capabilityStatus() => capability;

  // ====== 测试辅助 ======

  /// 模拟用户授权通知显示权限。
  void grantPermission() {
    _permission = ReminderPermissionStatus.granted;
    initialPermission = ReminderPermissionStatus.granted;
  }

  /// 模拟用户拒绝通知显示权限。
  void denyPermission() {
    _permission = ReminderPermissionStatus.denied;
    initialPermission = ReminderPermissionStatus.denied;
  }

  /// 模拟用户撤销精确提醒权限。
  void revokeExactAlarms() {
    canScheduleExactAlarmsFlag = false;
  }

  /// 模拟用户重新授予精确提醒权限。
  void grantExactAlarms() {
    canScheduleExactAlarmsFlag = true;
  }

  /// 显式设置权限状态(用于"权限被撤销后"等场景)。
  void setPermission(ReminderPermissionStatus status) {
    _permission = status;
    initialPermission = status;
  }

  /// 当前是否已调度指定 (taskId, offsetMinutes) 的提醒。
  bool hasScheduled(String taskId, int offsetMinutes) =>
      scheduled.containsKey(ReminderKey(taskId, offsetMinutes));

  /// 当前是否已调度指定 taskId 的任意提醒。
  bool hasScheduledForTask(String taskId) =>
      scheduled.keys.any((k) => k.taskId == taskId);

  /// 已调度条目数量。
  int get scheduledCount => scheduled.length;

  /// 是否打开了精确提醒设置页。
  bool get exactAlarmsSettingsOpened => _exactAlarmsOpened;

  /// 是否打开了通知设置页。
  bool get notificationSettingsOpened => _notificationSettingsOpened;

  /// refreshPermissionStatus 被调用次数。
  int get refreshCount => _refreshCount;

  /// 是否请求过权限。
  bool get permissionRequested => _permissionRequested;

  /// 清空所有调度记录(不影响权限状态)。
  void reset() {
    scheduled.clear();
    calls.clear();
    _scheduledIdsByTask.clear();
    _permissionRequested = false;
    _exactAlarmsOpened = false;
    _notificationSettingsOpened = false;
    _refreshCount = 0;
  }
}

/// (taskId, offsetMinutes) 组合键 — 用于 Fake 服务的 scheduled map。
class ReminderKey {
  const ReminderKey(this.taskId, this.offsetMinutes);

  final String taskId;
  final int offsetMinutes;

  @override
  bool operator ==(Object other) =>
      other is ReminderKey &&
      other.taskId == taskId &&
      other.offsetMinutes == offsetMinutes;

  @override
  int get hashCode => Object.hash(taskId, offsetMinutes);

  @override
  String toString() => 'ReminderKey($taskId, $offsetMinutes)';
}

/// Fake 提醒记录(测试用,公开以便测试断言读取字段)。
class FakeReminderRecord {
  const FakeReminderRecord({
    required this.notificationId,
    required this.title,
    required this.body,
    required this.scheduledAt,
  });

  final int notificationId;
  final String title;
  final String body;
  final DateTime scheduledAt;
}
