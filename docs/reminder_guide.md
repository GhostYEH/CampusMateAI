# 本地提醒功能指南(Android 精确提醒完整闭环)

## 概述

CampusMate AI 的本地提醒功能基于 `flutter_local_notifications` 插件,在 Android 系统层
调度**任务截止时间**的精确提醒。提醒在应用后台、屏幕锁定或 Doze 状态下也能由系统精确触发,
设备重启后系统会自动重新调度未来到期的任务。

提醒仅服务于"待办任务的截止时间",**不进行任何心理状态干预或情绪诊断**
(详见末尾科学边界)。

## 调度策略(Android 精确提醒)

### AndroidScheduleMode.exactAllowWhileIdle

调度使用 `AndroidScheduleMode.exactAllowWhileIdle`:

- **精确触发**:不批处理,在指定时刻准时触发(不受 Doze 影响)
- **AllowWhileIdle**:即使在 Doze / 待机状态下也能弹出通知
- **要求**:Android 12+ 需用户主动授予 `SCHEDULE_EXACT_ALARM` 权限

### 权限方案(只使用 SCHEDULE_EXACT_ALARM)

`AndroidManifest.xml` 中**仅声明**:

```xml
<uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM"/>
<uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED"/>
```

**不声明** `USE_EXACT_ALARM`。原因:

- `USE_EXACT_ALARM` 在 Google Play Store 上有更严格审核
- 不需用户主动授予,与本项目"用户可控授权"流程不符
- `SCHEDULE_EXACT_ALARM` 由用户在系统"闹钟和提醒"设置中授予,更可控

### AndroidManifest 必备声明

```xml
<!-- 通知显示权限(Android 13+ 运行时) -->
<uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>
<!-- 精确提醒权限(Android 12+ 用户主动授予) -->
<uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM"/>
<!-- 设备重启后恢复已调度提醒 -->
<uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED"/>

<application ...>
  <!-- 定时通知接收器(到点触发) -->
  <receiver
      android:name="com.dexterous.flutterlocalnotifications.ScheduledNotificationReceiver"
      android:exported="false" />
  <!-- 设备重启 / 应用更新后恢复 -->
  <receiver
      android:name="com.dexterous.flutterlocalnotifications.ScheduledNotificationBootReceiver"
      android:exported="false">
    <intent-filter>
      <action android:name="android.intent.action.BOOT_COMPLETED"/>
      <action android:name="android.intent.action.MY_PACKAGE_REPLACED"/>
      <action android:name="android.intent.action.QUICKBOOT_POWERON"/>
      <action android:name="com.htc.intent.action.QUICKBOOT_POWERON"/>
    </intent-filter>
  </receiver>
</application>
```

## 权限处理

### Android 13+ 双权限分离

Android 13+ 上,通知显示与精确提醒是**两个独立**的特殊访问权限:

| 权限 | 触发场景 | 申请方式 |
|------|---------|---------|
| POST_NOTIFICATIONS | 通知能否显示 | 运行时弹窗 / 系统设置 |
| SCHEDULE_EXACT_ALARM | 能否精确触发 | 系统"闹钟和提醒"设置页 |

### 调度前检查(强制顺序)

`scheduleReminder` 在调度前依次检查:

1. **通知权限**:若 `permissionStatus != granted`,尝试 `requestPermission()`
   - 仍失败 → 返回 `notificationPermissionDenied`,不调度
2. **精确提醒权限**:若 `canScheduleExactAlarms() == false`
   - **不静默降级为 inexact** → 返回 `exactAlarmPermissionDenied`
3. **时间合法性**:若 `scheduledAt` 不在未来
   - 返回 `pastTime`
4. **任务状态**:调用方 `TaskListNotifier._syncReminder` 已确保跳过已完成/已删除任务

### 精确权限被拒绝的处理(不静默降级)

精确权限被拒时:

- **不**调度任何提醒
- **不**显示"提醒已设置"
- 通过 UI 横幅提示"尚未获得精确提醒权限"
- 提供"前往闹钟和提醒"操作按钮,跳转系统设置
- 用户从系统设置返回后,`ReminderPermissionBanner` 通过 `WidgetsBindingObserver`
  的 `didChangeAppLifecycleState` 自动重新检查权限

### 权限礼貌策略

- **已授权** → 不再重复弹窗
- **已拒绝** → 不再自动请求系统弹窗,只在 UI 上展示引导横幅
- **未询问** → 首次调度前请求一次

## 时区修复

### 不使用 DateTime.now().timeZoneName

`DateTime.now().timeZoneName` 在 Android 上常返回缩写(如 "CST"),无法对应 IANA 数据库:

- 中国标准时间(CST)与美国中部时间(CST)缩写相同
- 不同 Android 版本返回值不一致
- 无法用于 `tz.setLocalLocation`

### 正确实现

通过 `flutter_timezone` 插件获取 IANA 时区名:

```dart
final localName = await FlutterTimezone.getLocalTimezone(); // "Asia/Shanghai"
final location = tz.getLocation(localName);
tz.setLocalLocation(location);
```

然后在调度时使用 `tz.TZDateTime.from(scheduledAt, tz.local)` 转换:

- 正确处理 UTC、本地时间、夏令时
- 不为时区插件盲目升级整个 Flutter 工程

## 稳定 notificationId

由 `taskId + offsetMinutes` 组合生成稳定 ID(FNV-1a 32-bit 哈希):

```dart
static int notificationIdFor(String taskId, int offsetMinutes) {
  // FNV-1a hash over "taskId|offsetMinutes"
  // ...
  return hash % 1000000;
}
```

**稳定性保证**:

- 同一 (taskId, offsetMinutes) 组合始终产生相同 ID
- 同一提醒更新时覆盖旧提醒(`zonedSchedule` 同 ID 会覆盖)
- 重启恢复时通过 `pendingNotificationRequests` 去重
- 不使用 Dart 默认 `Object.hashCode`(跨进程不稳定)

## 提醒生命周期

| 事件 | 行为 |
|------|------|
| 创建任务 | 创建精确提醒(若 `reminderEnabled && reminderAt != null`) |
| 修改截止时间 | `updateReminder` → cancelAllForTask + schedule(新 offset) |
| 修改提醒偏移 | 同步更新(新 offset 产生新 ID,旧 ID 被取消) |
| 关闭提醒 | `cancelAllForTask` |
| 完成任务 | `cancelAllForTask` |
| 删除任务 | `cancelAllForTask` |
| 恢复任务 | 根据 `reminderEnabled` 重新调度 |
| 恢复演示数据 | `restoreAllReminders` 通过 pending 去重,不产生大量重复通知 |

## 提醒恢复

### 设备重启 / 应用更新后

由 `ScheduledNotificationBootReceiver` 在系统层自动恢复(需 `RECEIVE_BOOT_COMPLETED`
权限与正确的 intent-filter)。

### 权限重新授予 / 进程重启后

通过 `reminderRestoreProvider` 在应用启动时调用 `restoreAllReminders`:

- 跳过已完成 / 已删除 / 已过期的任务
- 通过 `pendingNotificationRequests` 去重,**不重复创建**同一提醒
- 权限不足时返回 0,不假装恢复

### 调用时机

- 应用启动 `initState`(`lib/app/app.dart`)
- 用户从系统设置返回后(`ReminderPermissionBanner.didChangeAppLifecycleState`)

## 支持的提醒偏移

至少支持以下三种:

| 类型 | leadMinutes | 说明 |
|------|-------------|------|
| 截止前 2 小时 | 120 | 推荐,适合短期任务 |
| 截止前 24 小时 | 1440 | 适合需要提前准备的任务 |
| 自定义时间 | 任意 | 用户在 UI 上选择具体时刻 |

`ReminderSection` 提供预设 chip + 自定义 Dropdown,`TaskCreatePage` 提供更细粒度选项。

## Web 平台降级

Web 平台**不支持**后台精确调度:

- 所有调度方法返回 `unsupportedPlatform`
- UI 横幅显示"Web 端仅提供应用内提醒,精确系统提醒请使用 Android"
- **不**调用任何 Android 插件 API
- **不**声称支持后台精确调度

## 服务抽象

UI / Notifier 不直接依赖 `flutter_local_notifications` 插件,通过抽象接口 +
Riverpod Provider 注入:

```dart
abstract interface class NotificationReminderService {
  Future<bool> requestPermission();
  ReminderPermissionStatus permissionStatus();
  Future<void> refreshPermissionStatus();
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

`ReminderScheduleResult` 描述调度的具体结果,UI 据此决定反馈:

- `success`:可显示"提醒已设置"
- `exactAlarmPermissionDenied`:**不**显示"提醒已设置",提示前往系统设置
- `notificationPermissionDenied`:提示通知权限未授予
- `pastTime`:提示时间已过期
- `unsupportedPlatform`:Web 降级文案
- `pluginException`:不虚报成功,提示稍后重试

注入位置:

```dart
final notificationReminderProvider = Provider<NotificationReminderService>(
  (ref) => LocalNotificationReminderService(),
);
```

## 实现

| 实现 | 用途 | 说明 |
|------|------|------|
| `LocalNotificationReminderService` | 真实调度(Android/iOS) | `lib/data/services/local_notification_reminder_service.dart`,使用 `flutter_local_notifications` + `timezone` + `flutter_timezone` |
| `FakeNotificationReminderService` | 单元测试 / Widget 测试 | `lib/mock/mock_services/fake_notification_reminder_service.dart`,不依赖插件,记录所有调用并可控返回 |

## UI 集成

### 权限引导横幅

`ReminderPermissionBanner`(`lib/features/notifications/presentation/widgets/reminder_permission_banner.dart`)
是一个 `ConsumerStatefulWidget`,自动根据 `refreshedReminderStatusProvider` 展示对应横幅:

- Web 平台:降级说明(无操作按钮)
- 通知权限被拒:解释 + "前往设置" 按钮
- 精确权限未授:解释 + "前往闹钟和提醒" 按钮
- 全部满足:不渲染任何内容

内嵌于 `ReminderSection` 与 `TaskCreatePage._reminderSection` 中,统一视觉风格。

### 应用回前台自动刷新

`ReminderPermissionBanner` 通过 `WidgetsBindingObserver` 监听
`didChangeAppLifecycleState`,在 `resumed` 时递增
`reminderStatusRefreshTriggerProvider`,触发 `refreshedReminderStatusProvider`
重新计算 — 用户从系统设置返回后,横幅自动更新。

### 调度失败反馈

`ReminderScheduleFeedback.messageFor(result)` 根据调度结果返回对应文案:

- `null`:取消提醒 / 调度成功(由调用方控制)
- 其它:对应提示文案(包含"任务已保存"等澄清信息)

`TaskCreatePage._save` 与 `NotificationExtractPage._save` 在保存任务后,
读取 `taskListProvider.notifier.lastScheduleResult` 并展示对应反馈。
**任务本身仍保存成功**,仅提醒部分有独立的反馈通道。

## Mock 模式

Mock 模式下本地提醒**仍然工作**:

- `notificationReminderProvider` 默认注入 `LocalNotificationReminderService`,不依赖后端
- 后端 Mock / Real 切换只影响通知抽取、AI 导员、知识库等远端能力,**不影响**本地提醒
- 测试环境通过覆盖 Provider 为 `FakeNotificationReminderService` 实现完全离线的提醒行为验证

## 测试覆盖

测试位于:

- `test/mock/mock_services/fake_notification_reminder_service_test.dart`
  — Fake 服务的所有方法、稳定 ID、restore 去重
- `test/app/providers/task_list_reminder_integration_test.dart`
  — TaskListNotifier 与提醒服务的集成测试,覆盖:
  - 权限授予 / 拒绝 / 撤销场景
  - 精确权限未授权时不调度
  - 通知权限被拒时不调度
  - 插件异常时不虚报成功
  - 创建 / 更新 / 取消 / 完成 / 删除 / 恢复 生命周期
  - 过去时间不调度
  - 稳定 notificationId
  - 重启恢复去重
  - 演示数据恢复不产生重复通知
  - Web 平台降级
- `test/data/services/reminder_timezone_test.dart`
  — 时区转换、夏令时、IANA 名称解析
- `test/features/notifications/reminder_permission_banner_test.dart`
  — 横幅在不同权限状态下的展示

## 真机验证清单

> **当前状态:未完成真机验证**(单元测试与构建已通过,但未在真实 Android 设备上验证)

完成真机验证时,需验证以下场景:

- [ ] 授予通知权限
- [ ] 授予精确提醒权限(系统"闹钟和提醒"设置)
- [ ] 设置 2—3 分钟后的提醒
- [ ] 应用退到后台
- [ ] 锁屏
- [ ] 提醒在指定分钟触发
- [ ] 修改提醒后旧提醒不触发
- [ ] 重启设备后提醒仍存在
- [ ] 撤销精确权限后不再虚报设置成功

无法完成真机验证时,必须在交付说明中明确写"未完成真机验证",不能用单元测试冒充。

## 科学边界(强制)

本地提醒**仅用于任务截止时间**的定时通知,与以下内容无关:

- 不进行心理状态评估或情绪诊断
- 不基于表情识别结果触发"情绪安慰"通知
- 不替代专业心理咨询

CNN 表情识别与本地提醒是两条独立的链路:前者提供"可观察表情"的辅助参考,
后者只服务于"待办截止"的实用提醒。两者均不构成医疗或心理诊断。

参见 [`AGENTS.md`](../AGENTS.md) 第 3 节"科学边界"。
