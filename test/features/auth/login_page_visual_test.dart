import 'dart:io' show Platform;

import 'package:campus_companion/app/config/app_config.dart';
import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/app/theme/app_theme.dart';
import 'package:campus_companion/core/widgets/state_views.dart';
import 'package:campus_companion/features/auth/presentation/login_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets('登录页 Android 参考视口视觉基线', (tester) async {
    final textFont = FontLoader('NotoSansSC')
      ..addFont(rootBundle.load('assets/fonts/NotoSansSC-VF.ttf'));
    final iconFont = FontLoader('MaterialIcons')
      ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
    await Future.wait([textFont.load(), iconFont.load()]);

    SharedPreferences.setMockInitialValues({});
    await tester.binding.setSurfaceSize(const Size(362, 716));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    const goldenKey = ValueKey('login-page-golden');
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          appConfigProvider.overrideWith((ref) {
            return const AppConfig(
              environment: AppEnvironment.development,
              useMockBackend: true,
              useMockExpressionRecognition: true,
              apiBaseUrl: 'http://10.0.2.2:8000',
            );
          }),
          reduceMotionProvider.overrideWith((ref) => true),
        ],
        child: MaterialApp(
          theme: AppTheme.light(),
          home: const RepaintBoundary(
            key: goldenKey,
            child: LoginPage(),
          ),
        ),
      ),
    );
    await tester.pump();
    await tester.runAsync(() async {
      await precacheImage(
        const AssetImage('assets/images/auth/campus_night_portrait.png'),
        tester.element(find.byType(LoginPage)),
      );
    });
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pumpAndSettle();

    final goldenFile = Platform.isLinux
        ? 'goldens/login_page_362x716_linux.png'
        : 'goldens/login_page_362x716.png';
    await expectLater(
      find.byKey(goldenKey),
      matchesGoldenFile(goldenFile),
    );
  });
}
