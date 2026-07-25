import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../app/router/app_router.dart';
import '../app/theme/app_theme.dart';
import '../app/providers/app_providers.dart';
import '../core/widgets/state_views.dart';

class CampusCompanionApp extends ConsumerWidget {
  const CampusCompanionApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    final settings = ref.watch(appSettingsProvider);

    // 同步减少动态效果设置到全局 Provider
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(reduceMotionProvider.notifier).state = settings.reduceMotion;
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
