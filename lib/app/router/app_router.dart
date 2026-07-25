import 'package:go_router/go_router.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/home/presentation/home_page.dart';
import '../../features/tasks/presentation/tasks_page.dart';
import '../../features/counselor/presentation/counselor_page.dart';
import '../../features/study_companion/presentation/study_companion_page.dart';
import '../../features/profile/presentation/profile_page.dart';
import '../../features/notifications/presentation/notification_extract_page.dart';
import '../../features/notifications/presentation/notifications_list_page.dart';
import '../../features/tasks/presentation/task_create_page.dart';
import 'main_shell.dart';

final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: '/home',
    routes: [
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) {
          return MainShell(navigationShell: navigationShell);
        },
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/home',
                builder: (context, state) => const HomePage(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/tasks',
                builder: (context, state) => const TasksPage(),
                routes: [
                  GoRoute(
                    path: 'create',
                    builder: (context, state) => const TaskCreatePage(),
                  ),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/counselor',
                builder: (context, state) => const CounselorPage(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/study',
                builder: (context, state) => const StudyCompanionPage(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/profile',
                builder: (context, state) => const ProfilePage(),
              ),
            ],
          ),
        ],
      ),
      GoRoute(
        path: '/notifications',
        builder: (context, state) => const NotificationsListPage(),
      ),
      GoRoute(
        path: '/notifications/extract',
        builder: (context, state) => const NotificationExtractPage(),
      ),
    ],
  );
});
