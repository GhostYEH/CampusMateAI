# 本地提醒功能指南

## 概述

CampusMate AI 的本地提醒功能基于 `flutter_local_notifications` 插件,在 Android 系统层调度**任务截止时间**的定时通知。提醒在应用后台或未运行时也能由系统触发,设备重启后系统会自动重新调度未来到期的任务(`zonedSchedule` + `AndroidScheduleMode.inexactAllowWhileIdle`)。

提醒仅服务于"待办任务的截止时间",**不进行任何心理状态干预或情绪诊断**(详见末尾科学边界)。

## 功能特性

### 调度时机

- **保存带截止时间的任务时**:用户在创建/编辑待办并启用提醒后,系统自动调度一条定时通知
- **建议提醒时间**:在通知整理页与任务编辑页提供快捷选项
  - 截止时间前 2 小时
  - 截止时间前 24 小时
  - 自定义时间
- **添加 / 修改 / 取消**:用户可在任务详情或编辑页随时调整提醒时间或关闭提醒

### 状态同步

- **截止时间变更**:更新任务 `deadline` 后,已调度的提醒会自动 `cancel + schedule` 重新对齐(`updateReminder`)
- **任务完成**:任务标记为 `completed` 时,自动取消未触发的提醒,避免已完成任务仍弹出通知
- **任务删除**(软删除 / 硬删除):自动调用 `cancelAllForTask`,清理所有关联通知

### 权限处理

- Android 13+ 运行时请求 `POST_NOTIFICATIONS` 权限
- Android 12+ 请求 `SCHEDULE_EXACT_ALARM` 权限(已在 `AndroidManifest.xml` 声明)
- iOS 请求 `alert / badge / sound` 权限
- **礼貌策略**:
  - 已授权 → 不再重复弹窗
  - 已拒绝 → 不再自动请求,只在 UI 上显示解释说明并提供"前往系统设置"入口
  - 未询问 → 首次调度前请求一次

### 重启持久化与时区

- 使用 `zonedSchedule` + `tz.local` 提交调度,Android 系统在设备重启后会自动重新调度未到期的任务
- 时区通过 `timezone` 包在 `ReminderBootstrap.initialize()` 中初始化(应用启动时调用一次)
- 失败不抛异常,提醒功能不可用不会阻断应用启动

## 平台降级

### Web 端

Web 端当前仅提供应用内提醒,系统级定时通知请使用 Android 版本。

`LocalNotificationReminderService.capabilityStatus()` 在 Web 平台返回 `ReminderCapabilityStatus.degraded`,UI 层据此向用户解释平台限制并展示应用内提醒。

### iOS

iOS 当前接口已预留(`DarwinNotificationDetails`),但比赛演示与测试主要在 Android 与 Web 平台进行。

## 服务抽象

UI / Notifier 不直接依赖 `flutter_local_notifications` 插件,通过抽象接口 + Riverpod Provider 注入:

```dart
abstract interface class NotificationReminderService {
  Future<bool> requestPermission();
  Future<bool> scheduleReminder({
    required String taskId,
    required String title,
    required String body,
    required DateTime scheduledAt,
  });
  Future<void> cancelReminder(String taskId);
  Future<bool> updateReminder({
    required String taskId,
    required String title,
    required String body,
    required DateTime scheduledAt,
  });
  Future<void> cancelAllForTask(String taskId);
  ReminderCapabilityStatus capabilityStatus();
  ReminderPermissionStatus permissionStatus();
}
```

- `ReminderCapabilityStatus`: `supported` / `degraded` / `unknown`
- `ReminderPermissionStatus`: `granted` / `denied` / `notDetermined` / `unsupported`

注入位置:

```dart
final notificationReminderProvider = Provider<NotificationReminderService>(
  (ref) => LocalNotificationReminderService(),
);
```

`TaskListNotifier` 通过 `notificationReminderProvider` 注入提醒服务,在 `createTask` / `updateTask` / `toggleComplete` / `softDelete` / `hardDelete` 后调用 `_syncReminder(task)` 同步系统通知。提醒调度是"尽力而为" — 失败(权限未授予 / Web 平台 / 时间已过)不会阻断任务操作。

## 实现

| 实现 | 用途 | 说明 |
|------|------|------|
| `LocalNotificationReminderService` | 真实调度(Android / iOS) | 位于 `lib/data/services/local_notification_reminder_service.dart`,使用 `flutter_local_notifications` + `timezone` |
| `FakeNotificationReminderService` | 单元测试 / Widget 测试 | 位于 `lib/mock/mock_services/fake_notification_reminder_service.dart`,不依赖插件,记录所有调用并可控返回 |

`FakeNotificationReminderService` 在测试中通过 `ProviderScope.overrides` / `ProviderContainer.overrides` 注入,可模拟授权、拒绝、调度失败等场景,并暴露 `scheduled` / `calls` / `hasScheduled` 等字段便于断言。

## Mock 模式

Mock 模式下本地提醒**仍然工作**:

- `notificationReminderProvider` 默认注入 `LocalNotificationReminderService`,不依赖后端
- 后端 Mock / Real 切换只影响通知抽取、AI 导员、知识库等远端能力,**不影响**本地提醒
- 测试环境通过覆盖 Provider 为 `FakeNotificationReminderService` 实现完全离线的提醒行为验证

## 权限被拒绝的处理

- `requestPermission()` 返回 `false` 后,`scheduleReminder` 也会返回 `false`,但任务依然保存成功
- UI 层根据 `permissionStatus()` 显示:
  - 解释说明:为什么需要通知权限(用于截止时间提醒)
  - "前往系统设置"入口(打开应用设置页)
- 不再自动重复请求系统弹窗,避免打扰用户

## 科学边界(强制)

本地提醒**仅用于任务截止时间**的定时通知,与以下内容无关:

- 不进行心理状态评估或情绪诊断
- 不基于表情识别结果触发"情绪安慰"通知
- 不替代专业心理咨询

CNN 表情识别与本地提醒是两条独立的链路:前者提供"可观察表情"的辅助参考,后者只服务于"待办截止"的实用提醒。两者均不构成医疗或心理诊断。

参见 [`AGENTS.md`](../AGENTS.md) 第 3 节"科学边界"。
