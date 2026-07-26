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
class FakeNotificationReminderService implements NotificationReminderService {
  FakeNotificationReminderService({
    this.capability = ReminderCapabilityStatus.supported,
    this.initialPermission = ReminderPermissionStatus.notDetermined,
    this.shouldFailScheduling = false,
  });

  ReminderCapabilityStatus capability;
  ReminderPermissionStatus initialPermission;
  bool shouldFailScheduling;

  /// 已调度的提醒: taskId -> (title, body, scheduledAt)
  final Map<String, FakeReminderRecord> scheduled = {};

  /// 调用记录(便于断言)。
  final List<String> calls = [];

  bool _permissionRequested = false;

  @override
  Future<bool> requestPermission() async {
    calls.add('requestPermission');
    _permissionRequested = true;
    return initialPermission == ReminderPermissionStatus.granted ||
        initialPermission == ReminderPermissionStatus.notDetermined;
  }

  @override
  Future<bool> scheduleReminder({
    required String taskId,
    required String title,
    required String body,
    required DateTime scheduledAt,
  }) async {
    calls.add('scheduleReminder:$taskId');
    if (shouldFailScheduling) return false;
    if (initialPermission == ReminderPermissionStatus.denied ||
        initialPermission == ReminderPermissionStatus.unsupported) {
      return false;
    }
    if (!scheduledAt.isAfter(DateTime.now())) return false;
    scheduled[taskId] = FakeReminderRecord(
      title: title,
      body: body,
      scheduledAt: scheduledAt,
    );
    return true;
  }

  @override
  Future<void> cancelReminder(String taskId) async {
    calls.add('cancelReminder:$taskId');
    scheduled.remove(taskId);
  }

  @override
  Future<bool> updateReminder({
    required String taskId,
    required String title,
    required String body,
    required DateTime scheduledAt,
  }) async {
    calls.add('updateReminder:$taskId');
    scheduled.remove(taskId);
    return scheduleReminder(
      taskId: taskId,
      title: title,
      body: body,
      scheduledAt: scheduledAt,
    );
  }

  @override
  Future<void> cancelAllForTask(String taskId) async {
    calls.add('cancelAllForTask:$taskId');
    scheduled.remove(taskId);
  }

  @override
  ReminderCapabilityStatus capabilityStatus() => capability;

  @override
  ReminderPermissionStatus permissionStatus() {
    if (_permissionRequested) return initialPermission;
    return initialPermission;
  }

  /// 测试辅助: 模拟用户授权。
  void grantPermission() {
    initialPermission = ReminderPermissionStatus.granted;
  }

  /// 测试辅助: 模拟用户拒绝。
  void denyPermission() {
    initialPermission = ReminderPermissionStatus.denied;
  }

  /// 测试辅助: 当前是否已调度指定 taskId 的提醒。
  bool hasScheduled(String taskId) => scheduled.containsKey(taskId);

  /// 测试辅助: 清空所有调度记录(不影响权限状态)。
  void reset() {
    scheduled.clear();
    calls.clear();
    _permissionRequested = false;
  }
}

/// Fake 提醒记录(测试用,公开以便测试断言读取字段)。
class FakeReminderRecord {
  const FakeReminderRecord({
    required this.title,
    required this.body,
    required this.scheduledAt,
  });

  final String title;
  final String body;
  final DateTime scheduledAt;
}
