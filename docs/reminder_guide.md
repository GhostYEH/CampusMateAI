# 本地提醒功能指南

## 概述

CampusMate AI 的本地提醒功能基于 `flutter_local_notifications` 插件,在 Android 系统层调度**任务截止时间**的精确提醒(`AndroidScheduleMode.exactAllowWhileIdle`)。提醒在应用后台或未运行时也能由系统精确触发,设备重启 / 应用更新后系统会自动重新调度未来到期的任务。

提醒仅服务于"待办任务的截止时间",**不进行任何心理状态干预或情绪诊断**(详见末尾科学边界)。

## Android 精确提醒方案(对齐 AGENTS.md "Android 精确提醒完整闭环")

### 调度模式

- 使用 `AndroidScheduleMode.exactAllowWhileIdle` —— 精确触发,且设备 Doze/idle 状态下也能弹出
- **不静默降级**为 inexact:精确权限被拒时直接返回 `exactAlarmPermissionDenied`,UI 显示明确提示并引导用户授权
- **不声明** `USE_EXACT_ALARM`(Play Store 审核更严,且不需用户主动授予,与本项目"用户主动授予精确提醒权限"的可控流程不符)
- 仅声明 `SCHEDULE_EXACT_ALARM`,由用户在系统"闹钟和提醒"设置中主动授予

### 权限方案(`AndroidManifest.xml`)

```xml
<!-- 通知显示权限(Android 13+ 运行时请求) -->
<uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>
<!-- 精确提醒权限(Android 12+,需用户在"闹钟和提醒"设置中授予) -->
<uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM"/>
<!-- 设备重启后恢复已调度的精确提醒 -->
<uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED"/>

<!-- flutter_local_notifications 接收器(到点触发) -->
<receiver android:name="com.dexterous.flutterlocalnotifications.ScheduledNotificationReceiver" />

<!-- 设备重启 / 应用更新 / 厂商快速开机后恢复已调度的精确提醒。
     intent-filter actions 按 flutter_local_notifications 官方文档配置。 -->
<receiver android:name="com.dexterous.flutterlocalnotifications.ScheduledNotificationBootReceiver">
    <intent-filter>
        <action android:name="android.intent.action.BOOT_COMPLETED"/>
        <action android:name="android.intent.action.MY_PACKAGE_REPLACED"/>
        <action android:name="android.intent.action.QUICKBOOT_POWERON"/>
        <action android:name="com.htc.intent.action.QUICKBOOT_POWERON"/>
    </intent-filter>
</receiver>
```

### Android 13+ 双权限分别处理

| 权限 | 触发条件 | 拒绝时行为 |
|------|----------|------------|
| `POST_NOTIFICATIONS`(通知显示) | 运行时弹窗 | UI 显示横幅 + "前往通知设置"按钮 |
| `SCHEDULE_EXACT_ALARM`(精确提醒) | 用户在"闹钟和提醒"设置中授予 | UI 显示横幅 + "前往闹钟和提醒设置"按钮,**不静默降级** |

### 调度前置检查(任一失败则返回对应失败原因,**不**静默降级)

1. 通知权限已授予(否则尝试请求一次,仍失败则返回 `notificationPermissionDenied`)
2. Android 上 `canScheduleExactAlarms` 为 true(否则返回 `exactAlarmPermissionDenied`)
3. `scheduledAt` 在未来(否则返回 `pastTime`)
4. 任务未完成 / 未删除(由 `TaskListNotifier` 在调用前过滤)
5. 插件调用未抛异常(否则返回 `pluginException`)
6. Web 平台直接返回 `unsupportedPlatform`(**不**调用任何 Android 插件 API)

### 权限被拒绝后的处理

- **不**显示"提醒已设置"
- **不**静默改用非精确提醒
- 显示明确提示:"尚未获得精确提醒权限"
- 提供"前往闹钟和提醒设置"入口(`openExactAlarmSettings`)
- 用户从系统设置返回应用后,自动重新检查权限(`didChangeAppLifecycleState` → `refresh`)

### 权限被撤销后

- `capabilityStatus` / `reminderStatusProvider` 正确变化
- 新提醒**不**假装创建成功
- 已持久化的任务提醒状态通过 `restoreAllReminders` 与系统状态同步

## 提醒生命周期

| 时机 | 行为 |
|------|------|
| 创建任务 | 调度精确提醒(`scheduleReminder`) |
| 修改截止时间 | 取消旧提醒 + 调度新提醒(`updateReminder`) |
| 修改提醒偏移 | 同步更新(取消旧偏移 + 调度新偏移) |
| 关闭提醒 | `cancelAllForTask` |
| 完成任务 | 取消未触发的提醒 |
| 删除任务(软 / 硬) | `cancelAllForTask` |
| 恢复任务 | 根据当前设置重新调度 |
| 恢复演示数据 | 通过 `restoreReminders` 去重,不产生大量重复系统通知 |

## 稳定通知 ID

每个 `(taskId, offsetMinutes)` 组合通过 FNV-1a 32-bit 哈希生成确定的 16-bit 通知 ID(0..65535,避开系统保留的 0):

```dart
int notificationIdFor(String taskId, int offsetMinutes) {
  final key = '$taskId:$offsetMinutes';
  var hash = 0x811C9DC5;
  for (final c in key.codeUnits) {
    hash ^= c;
    hash = (hash * 0x01000193) & 0xFFFFFFFF;
  }
  final folded = (hash ^ (hash >> 16)) & 0xFFFF;
  return folded == 0 ? 1 : folded;
}
```

- 跨进程稳定(不依赖 Dart 默认 `hashCode`)
- 同一提醒更新时由 `zonedSchedule` 覆盖旧提醒(同 ID)
- 不同 `offsetMinutes` 生成不同 ID,支持单任务多偏移

## 重启 / 应用更新 / 权限重授后恢复

- **AndroidManifest** 注册 `ScheduledNotificationBootReceiver`,系统重启 / 应用更新后由插件自动恢复已调度任务
- 应用启动时调用 `TaskListNotifier.restoreAllReminders()` 主动补齐:
  - 已完成 / 已删除 / 已过期的任务不恢复
  - 同一 `(taskId, offsetMinutes)` 已存在的不重复调度
  - 返回实际恢复的提醒数量
- 精确权限重新授予后,UI 通过 `reminderStatusProvider.notifier.refresh()` 触发状态同步,并可主动调用 `restoreAllReminders` 补齐

## 时区处理

- **不**使用 `DateTime.now().timeZoneName`(在 Android 上常返回 "CST" / "PST" 等非 IANA 缩写,会被 `tz.getLocation` 拒绝导致回退到 UTC)
- 通过 `flutter_timezone` 插件取得 IANA 时区名称(如 "Asia/Shanghai")
- 在 `ReminderBootstrap.initialize()` 中调用 `tz.setLocalLocation` 设置本地时区
- 使用 `tz.TZDateTime.from(scheduledAt, tz.local)` 转换为带时区的时刻
- 正确处理 UTC、本地时间和夏令时
- `uiLocalNotificationDateInterpretation: UILocalNotificationDateInterpretation.absoluteTime` 确保按本地绝对时间触发

## 提醒时间预设

至少支持以下三种:

- 截止前 24 小时(`offsetMinutes = 1440`)
- 截止前 2 小时(`offsetMinutes = 120`)— 默认值
- 用户自定义精确时间(`ReminderSection` 提供下拉选项: 30 分钟 / 1 小时 / 2 小时 / 6 小时 / 1 天 / 2 天)

## 平台降级

### Web 端

- `capabilityStatus()` 返回 `ReminderCapabilityStatus.degraded`
- `scheduleReminder` 返回 `unsupportedPlatform`,**不**调用任何 Android 插件 API
- UI 显示:"Web 端仅提供应用内提醒,精确系统提醒请使用 Android"
- **不**声称支持后台精确调度

### iOS

- 接口已预留(`DarwinNotificationDetails`),`canScheduleExactAlarms` 返回 true(iOS 无此概念)
- 比赛演示与测试主要在 Android 与 Web 平台进行

## 服务抽象

UI / Notifier 不直接依赖 `flutter_local_notifications` 插件,通过抽象接口 + Riverpod Provider 注入:

```dart
abstract interface class NotificationReminderService {
  Future<bool> requestPermission();
  Future<void> refreshPermissionStatus();
  ReminderPermissionStatus permissionStatus();
  Future<bool> canScheduleExactAlarms();
  Future<void> openExactAlarmSettings();
  Future<void> openNotificationSettings();

  Future<ReminderScheduleResult> scheduleReminder({
    required String taskId,
    required int offsetMinutes,
    required String title,
    required String body,
    required DateTime scheduledAt,
  });
  Future<void> cancelReminder(String taskId, int offsetMinutes);
  Future<void> cancelAllForTask(String taskId);
  Future<ReminderScheduleResult> updateReminder({
    required String taskId,
    required int offsetMinutes,
    required String title,
    required String body,
    required DateTime scheduledAt,
  });
  Future<int> restoreReminders(List<ReminderEntry> entries);
  ReminderCapabilityStatus capabilityStatus();
}
```

- `ReminderCapabilityStatus`: `supported` / `degraded` / `unknown`
- `ReminderPermissionStatus`: `granted` / `denied` / `notDetermined` / `unsupported`
- `ReminderScheduleResult`: `success(notificationId)` / `failed(failure)`
- `ReminderScheduleFailure`: `unsupportedPlatform` / `notificationPermissionDenied` / `exactAlarmPermissionDenied` / `pastTime` / `pluginException`

注入位置:

```dart
final notificationReminderProvider = Provider<NotificationReminderService>(
  (ref) => LocalNotificationReminderService(),
);

final reminderStatusProvider =
    StateNotifierProvider<ReminderStatusNotifier, ReminderStatusSnapshot>(
  (ref) {
    final service = ref.watch(notificationReminderProvider);
    return ReminderStatusNotifier(service);
  },
);
```

`TaskListNotifier` 通过 `notificationReminderProvider` 注入提醒服务,在 `createTask` / `updateTask` / `toggleComplete` / `softDelete` / `hardDelete` / `restore` 后调用 `_syncReminder(task)` 同步系统通知。

提醒调度是"不静默降级" —— 失败时通过 `ReminderScheduleFeedback` 向 UI 解释并引导去系统设置授权,任务操作本身不被阻断。

## UI 集成

### `ReminderSection` 组件

位于 `lib/features/notifications/presentation/widgets/reminder_section.dart`,在通知整理页与新建待办页共用:

- 监听 `reminderStatusProvider`,权限缺失时显示 `ReminderPermissionBanner`
- 切换开关前先检查权限,缺失则不切换而是显示横幅
- 监听 `WidgetsBindingObserver.didChangeAppLifecycleState`,用户从系统设置返回后主动刷新权限
- 提供预设(截止前 2 小时 / 24 小时)与自定义下拉
- 显示提醒时间预览(过期则提示"将不会触发系统通知")

### `ReminderPermissionBanner` 组件

位于 `lib/features/notifications/presentation/widgets/reminder_permission_banner.dart`:

- 三种类型: `notificationDenied` / `exactAlarmDenied` / `webDegraded`
- 提供"前往通知设置" / "前往闹钟和提醒设置"按钮
- 点击后调用对应 `openXxxSettings()` 并主动刷新权限

## 实现

| 实现 | 用途 | 说明 |
|------|------|------|
| `LocalNotificationReminderService` | 真实调度(Android / iOS) | 位于 `lib/data/services/local_notification_reminder_service.dart`,使用 `flutter_local_notifications` + `timezone` + `flutter_timezone` |
| `FakeNotificationReminderService` | 单元测试 / Widget 测试 | 位于 `lib/mock/mock_services/fake_notification_reminder_service.dart`,不依赖插件,记录所有调用并可控返回 |

`FakeNotificationReminderService` 在测试中通过 `ProviderScope.overrides` / `ProviderContainer.overrides` 注入,可模拟授权、拒绝、调度失败、插件异常、Web 降级等场景,并暴露 `scheduled` / `calls` / `hasScheduled` 等字段便于断言。

## Mock 模式

Mock 模式下本地提醒**仍然工作**:

- `notificationReminderProvider` 默认注入 `LocalNotificationReminderService`,不依赖后端
- 后端 Mock / Real 切换只影响通知抽取、AI 导员、知识库等远端能力,**不影响**本地提醒
- 测试环境通过覆盖 Provider 为 `FakeNotificationReminderService` 实现完全离线的提醒行为验证

## 测试覆盖

测试文件:

- `test/mock/mock_services/fake_notification_reminder_service_test.dart` — 服务层单元测试
- `test/features/notifications/notification_extract_page_test.dart` — 页面 Widget 测试

覆盖场景(对齐 AGENTS.md §14):

- 权限授予 / 拒绝 / 撤销
- 精确权限未授权时不调度(返回 `exactAlarmPermissionDenied`,**不**静默降级)
- `exactAllowWhileIdle` 被真实调用(由 `LocalNotificationReminderService` 调用 `zonedSchedule`)
- 创建 / 更新 / 取消 / 完成 / 删除生命周期
- 过去时间不调度
- 稳定通知 ID(同 `(taskId, offsetMinutes)` 多次调度返回相同 ID)
- 重启恢复去重(同条目多次 `restoreReminders` 不重复创建)
- 时区转换(由 `tz.TZDateTime.from` 处理)
- Web 安全降级(`unsupportedPlatform` 不调用 Android API)
- 插件异常时不虚报成功(返回 `pluginException`)

## 真机验证(待完成)

以下设备行为**尚未完成真机验证**(单元测试与构建通过,但不能替代真机):

- 授予通知权限
- 授予精确提醒权限
- 设置 2—3 分钟后的提醒
- 应用退到后台
- 锁屏
- 提醒在指定分钟触发
- 修改提醒后旧提醒不触发
- 重启设备后提醒仍存在
- 撤销精确权限后不再虚报设置成功

## 科学边界(强制)

本地提醒**仅用于任务截止时间**的定时通知,与以下内容无关:

- 不进行心理状态评估或情绪诊断
- 不基于表情识别结果触发"情绪安慰"通知
- 不替代专业心理咨询

CNN 表情识别与本地提醒是两条独立的链路:前者提供"可观察表情"的辅助参考,后者只服务于"待办截止"的实用提醒。两者均不构成医疗或心理诊断。

参见 [`AGENTS.md`](../AGENTS.md) 第 3 节"科学边界"。
