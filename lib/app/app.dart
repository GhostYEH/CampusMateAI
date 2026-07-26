import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/models/models.dart';
import '../app/router/app_router.dart';
import '../app/theme/app_theme.dart';
import '../app/providers/app_providers.dart';
import '../core/storage/data_persistence_service.dart';
import '../core/widgets/state_views.dart';

class CampusCompanionApp extends ConsumerStatefulWidget {
  const CampusCompanionApp({super.key});

  @override
  ConsumerState<CampusCompanionApp> createState() => _CampusCompanionAppState();
}

class _CampusCompanionAppState extends ConsumerState<CampusCompanionApp> {
  @override
  void initState() {
    super.initState();
    // 应用启动后恢复精确提醒(设备重启 / 应用更新 / 权限重新授予后)。
    // 放在 postFrame 中避免在 build 阶段触发 Provider 状态变更。
    // restoreReminders 内部通过 pendingNotificationRequests 去重,重复调用安全。
    WidgetsBinding.instance.addPostFrameCallback((_) {
      // 读取一次以触发 FutureProvider 计算
      ref.read(reminderRestoreProvider);
      // 同时初始化权限状态快照(用于 UI 横幅)
      ref.read(refreshedReminderStatusProvider);
    });
  }

  @override
  Widget build(BuildContext context) {
    final router = ref.watch(routerProvider);
    final settings = ref.watch(appSettingsProvider);

    // 同步减少动态效果设置到全局 Provider
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(reduceMotionProvider.notifier).state = settings.reduceMotion;
    });

    // 监听设置变化,自动持久化(fireImmediately: false 避免覆盖刚加载的数据)
    ref.listen<AppSettings>(appSettingsProvider, (_, next) {
      ref.read(dataPersistenceProvider).saveSettings(next);
    });

    // 监听任务列表变化,自动持久化
    ref.listen<List<Task>>(taskListProvider, (_, __) {
      ref.read(dataPersistenceProvider).saveTasks();
    });

    // 监听通知列表变化,自动持久化已读状态
    ref.listen<List<CampusNotice>>(campusNoticesProvider, (_, next) {
      ref.read(dataPersistenceProvider).saveNotices(next);
    });

    return MaterialApp.router(
      title: '校园事务智能陪伴助手',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      themeMode: settings.darkMode ? ThemeMode.dark : ThemeMode.light,
      routerConfig: router,
      builder: (context, child) {
        return MediaQuery(
          data: MediaQuery.of(context).copyWith(
            textScaler: TextScaler.noScaling.clamp(maxScaleFactor: 1.2),
          ),
          child: child!,
        );
      },
    );
  }
}
