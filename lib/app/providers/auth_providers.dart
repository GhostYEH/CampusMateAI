import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/storage/local_storage.dart';
import '../../data/models/models.dart';
import '../../data/services/api/api_client.dart';
import '../../data/services/api/api_multi_role_services.dart';
import '../../data/services/api/api_task_repository.dart';
import '../../data/services/api/auth_interceptor.dart';
import '../../data/services/api/token_storage.dart';
import '../../data/services/multi_role_service_interfaces.dart';
import '../../mock/mock_data/mock_data.dart';
import '../../mock/mock_services/mock_multi_role_services.dart';
import 'app_providers.dart';

/// 认证状态。
enum AuthStatus {
  /// 尚未初始化(应用启动时,正在从持久化加载会话)。
  initial,

  /// 已认证 — 用户已登录,session 可用。
  authenticated,

  /// 未认证 — 用户未登录或会话已过期。
  unauthenticated,

  /// 登录中(用于登录页按钮显示 loading)。
  loading,
}

/// 认证状态数据。
class AuthState {
  const AuthState({
    this.status = AuthStatus.initial,
    this.session,
    this.errorMessage,
  });

  final AuthStatus status;
  final AuthSession? session;
  final String? errorMessage;

  /// 当前登录用户(若有)。
  AppUser? get user => session?.user;

  bool get isAuthenticated => status == AuthStatus.authenticated;
  bool get isInitial => status == AuthStatus.initial;
  bool get isLoading => status == AuthStatus.loading;

  AuthState copyWith({
    AuthStatus? status,
    AuthSession? session,
    String? errorMessage,
  }) {
    return AuthState(
      status: status ?? this.status,
      session: session ?? this.session,
      errorMessage: errorMessage,
    );
  }

  static const empty = AuthState(status: AuthStatus.unauthenticated);
}

/// 认证状态 Notifier — 负责登录/登出/自动登录/refresh 失败处理。
///
/// 严格遵循 AGENTS.md 凭证规范:
/// - 401 时尝试一次 refresh(由 [AuthInterceptor] 处理,这里只接收回调)
/// - refresh 失败后退出到登录页(由 [AuthInterceptor.onSessionExpired] 触发)
/// - 防止多个并发请求重复刷新 token(由 [AuthInterceptor] 内部 Completer 保证)
class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier(this._ref) : super(const AuthState(status: AuthStatus.initial)) {
    _init();
  }

  final Ref _ref;

  /// 自动登录监听取消器。
  StreamSubscription? _autoLoginSub;

  /// 初始化 — 尝试从持久化恢复会话。
  ///
  /// Mock 模式下直接进入未认证状态(由登录页选择演示账号)。
  /// Real 模式下从 [TokenStorage] 读取会话,若有效则尝试 getCurrentUser 验证。
  Future<void> _init() async {
    final config = _ref.read(appConfigProvider);
    if (config.useMockBackend) {
      // Mock 模式: 直接进入未认证状态,等待用户选择演示账号
      state = AuthState.empty;
      return;
    }

    final tokenStorage = _ref.read(tokenStorageProvider);
    final session = await tokenStorage.loadSession();
    if (session == null) {
      state = AuthState.empty;
      return;
    }

    // session 存在 — 标记为 authenticated,后续请求会自动用 token
    // 若 token 已过期,首次请求会触发 refresh(由 AuthInterceptor 处理)
    state = AuthState(status: AuthStatus.authenticated, session: session);

    // 后台异步验证 session 是否仍然有效
    _validateSession(session);
  }

  Future<void> _validateSession(AuthSession session) async {
    try {
      final authService = _ref.read(authServiceProvider);
      final user = await authService.getCurrentUser();
      if (!mounted) return;
      state = AuthState(
        status: AuthStatus.authenticated,
        session: session.copyWith(user: user),
      );
    } catch (_) {
      // 验证失败 — 保留 session,后续请求若 401 会触发退出
      // 这里不主动退出,避免短暂网络问题导致用户被登出
    }
  }

  /// 登录。
  ///
  /// 成功后:
  /// - 持久化会话(TokenStorage)
  /// - 更新 currentUserProvider(通过 session.user)
  /// - 注入到 Mock services 的 setCurrentUser(若 Mock 模式)
  Future<AuthSession?> login(LoginCredentials credentials) async {
    state = state.copyWith(status: AuthStatus.loading, errorMessage: null);
    try {
      final authService = _ref.read(authServiceProvider);
      final session = await authService.login(credentials);

      // 持久化会话(Real 模式)
      final config = _ref.read(appConfigProvider);
      if (!config.useMockBackend) {
        await _ref.read(tokenStorageProvider).saveSession(session);
      }

      // 同步当前用户到旧版 currentUserProvider,保证旧页面继续工作
      _ref.read(currentUserProvider.notifier).state = session.user;

      // Mock 模式下,把用户注入到各 Mock service 的 setCurrentUser
      if (config.useMockBackend) {
        _injectMockCurrentUser(session.user);
      } else {
        // 真实后端模式:登录成功后,主动拉取当前用户的个人待办,
        // 避免 UI 首次渲染时显示空列表(对齐 Flutter 要求 #9:可保留只读缓存)。
        // 失败不阻塞登录,UI 会通过 TaskListNotifier 监听并展示错误。
        try {
          final repo = _ref.read(taskRepositoryProvider);
          if (repo is ApiTaskRepository) {
            await repo.refresh();
          }
        } catch (_) {
          // 网络错误不阻塞登录,用户进入页面后会看到错误提示
        }
      }

      state = AuthState(
        status: AuthStatus.authenticated,
        session: session,
      );
      return session;
    } on ApiException catch (e) {
      state = state.copyWith(
        status: AuthStatus.unauthenticated,
        errorMessage: e.message,
      );
      return null;
    } catch (e) {
      state = state.copyWith(
        status: AuthStatus.unauthenticated,
        errorMessage: '登录失败,请重试',
      );
      return null;
    }
  }

  /// 登出。
  Future<void> logout() async {
    final session = state.session;
    state = state.copyWith(status: AuthStatus.loading);

    try {
      if (session != null) {
        final authService = _ref.read(authServiceProvider);
        await authService.logout(session.refreshToken);
      }
    } catch (_) {
      // 忽略后端错误,本地仍要清理
    }

    final config = _ref.read(appConfigProvider);
    if (!config.useMockBackend) {
      await _ref.read(tokenStorageProvider).clear();
    }

    // 重置旧版 currentUserProvider 到默认值,避免页面残留登录状态
    _ref.read(currentUserProvider.notifier).state = MockData.currentUser;

    // 真实后端模式:登出时清空本地任务缓存,
    // 避免下一位登录用户看到上一位用户的任务(对齐 Flutter 要求 #11)。
    if (!config.useMockBackend) {
      try {
        final repo = _ref.read(taskRepositoryProvider);
        if (repo is ApiTaskRepository) {
          await repo.clearAll();
        }
      } catch (_) {
        // 清空缓存失败不阻塞登出
      }
    }

    state = AuthState.empty;
  }

  /// 由 [AuthInterceptor] 在 401 refresh 失败时触发。
  /// 退出到登录页并清理会话。
  Future<void> handleSessionExpired() async {
    final config = _ref.read(appConfigProvider);
    if (!config.useMockBackend) {
      await _ref.read(tokenStorageProvider).clear();
    }
    _ref.read(currentUserProvider.notifier).state = MockData.currentUser;
    state = AuthState.empty;
  }

  /// Mock 模式下注入当前用户到所有 Mock service。
  ///
  /// 这样 Mock service 在角色相关的过滤逻辑中可以使用当前用户信息。
  void _injectMockCurrentUser(AppUser user) {
    final config = _ref.read(appConfigProvider);
    if (!config.useMockBackend) return;

    // 使用 Provider 读取后通过类型检查注入
    final courseSvc = _ref.read(courseServiceProvider);
    if (courseSvc is MockCourseService) {
      courseSvc.setCurrentUser(user);
    }
    final announcementSvc = _ref.read(announcementServiceProvider);
    if (announcementSvc is MockAnnouncementService) {
      announcementSvc.setCurrentUser(user);
    }
    final assignmentSvc = _ref.read(assignmentServiceProvider);
    if (assignmentSvc is MockAssignmentService) {
      assignmentSvc.setCurrentUser(user);
    }
    final submissionSvc = _ref.read(submissionServiceProvider);
    if (submissionSvc is MockSubmissionService) {
      submissionSvc.setCurrentUser(user);
    }
    final dashboardSvc = _ref.read(dashboardServiceProvider);
    if (dashboardSvc is MockDashboardService) {
      dashboardSvc.setCurrentUser(user);
    }
  }

  /// 清除错误信息(用于登录页关闭错误提示)。
  void clearError() {
    if (state.errorMessage != null) {
      state = state.copyWith(errorMessage: null);
    }
  }

  @override
  void dispose() {
    _autoLoginSub?.cancel();
    super.dispose();
  }
}

/// Token 存储 Provider(单例,使用 SharedPreferencesLocalStorage)。
final tokenStorageProvider = Provider<TokenStorage>((ref) {
  // 使用 SharedPreferencesLocalStorage.instance,需在 main 中先 initialize
  final localStorage = SharedPreferencesLocalStorage.instance;
  return TokenStorage(localStorage);
});

/// 认证拦截器 Provider — 仅在 Real 模式下创建,Mock 模式返回 null。
///
/// 注意:此处使用独立的 [Dio] 实例发起 refresh 请求,避免与
/// [authedApiClientProvider] 形成循环依赖:
/// `authInterceptorProvider -> authedApiClientProvider -> authInterceptorProvider`。
/// refresh 请求通过 [_skipAuth] 标记不会被自身拦截器再次拦截。
final authInterceptorProvider = Provider<AuthInterceptor?>((ref) {
  final config = ref.watch(appConfigProvider);
  if (config.useMockBackend) return null;

  final tokenStorage = ref.watch(tokenStorageProvider);
  // 独立 Dio 用于 refresh 请求(避免依赖 authedApiClientProvider 导致的循环)
  final refreshDio = Dio(BaseOptions(baseUrl: config.apiBaseUrl));
  return AuthInterceptor(
    tokenStorage: tokenStorage,
    dio: refreshDio,
    refreshPath: '/api/v1/auth/refresh',
    onSessionExpired: () {
      // 异步触发 AuthNotifier.handleSessionExpired
      // 通过下一帧避免在拦截器回调中同步调用 Notifier 方法导致循环
      Future.microtask(() {
        ref.read(authNotifierProvider.notifier).handleSessionExpired();
      });
    },
  );
});

/// 认证后的 ApiClient(已注入 [AuthInterceptor])。
///
/// 与 [apiClientProvider] 区分:后者是裸 Dio,前者用于需要认证的请求。
/// Mock 模式下两者行为相同(Mock service 不会发起真实请求)。
final authedApiClientProvider = Provider<ApiClient>((ref) {
  final config = ref.watch(appConfigProvider);
  final client = ApiClient(baseUrl: config.apiBaseUrl);
  final interceptor = ref.watch(authInterceptorProvider);
  if (interceptor != null) {
    client.dio.interceptors.add(interceptor);
  }
  return client;
});

/// 认证服务 Provider — Mock / Real 通过 AppConfig 切换。
final authServiceProvider = Provider<AuthService>((ref) {
  final config = ref.watch(appConfigProvider);
  if (!config.useMockBackend) {
    return ApiAuthService(ref.watch(authedApiClientProvider));
  }
  return MockAuthService();
});

/// 课程服务 Provider。
final courseServiceProvider = Provider<CourseService>((ref) {
  final config = ref.watch(appConfigProvider);
  if (!config.useMockBackend) {
    return ApiCourseService(ref.watch(authedApiClientProvider));
  }
  return MockCourseService();
});

/// 通知服务 Provider。
final announcementServiceProvider = Provider<AnnouncementService>((ref) {
  final config = ref.watch(appConfigProvider);
  if (!config.useMockBackend) {
    return ApiAnnouncementService(ref.watch(authedApiClientProvider));
  }
  return MockAnnouncementService();
});

/// 任务服务 Provider。
final assignmentServiceProvider = Provider<AssignmentService>((ref) {
  final config = ref.watch(appConfigProvider);
  if (!config.useMockBackend) {
    return ApiAssignmentService(ref.watch(authedApiClientProvider));
  }
  return MockAssignmentService();
});

/// 提交服务 Provider。
final submissionServiceProvider = Provider<SubmissionService>((ref) {
  final config = ref.watch(appConfigProvider);
  if (!config.useMockBackend) {
    return ApiSubmissionService(ref.watch(authedApiClientProvider));
  }
  return MockSubmissionService();
});

/// 仪表盘服务 Provider。
final dashboardServiceProvider = Provider<DashboardService>((ref) {
  final config = ref.watch(appConfigProvider);
  if (!config.useMockBackend) {
    return ApiDashboardService(ref.watch(authedApiClientProvider));
  }
  return MockDashboardService();
});

/// 用户管理服务 Provider(管理员)。
final userManagementServiceProvider = Provider<UserManagementService>((ref) {
  final config = ref.watch(appConfigProvider);
  if (!config.useMockBackend) {
    return ApiUserManagementService(ref.watch(authedApiClientProvider));
  }
  return MockUserManagementService();
});

/// 认证状态 Notifier Provider。
final authNotifierProvider =
    StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier(ref);
});

/// 当前登录用户(从 [AuthNotifier] 派生)。
///
/// 这是 role-aware 版本的 currentUser — 登录后返回真实用户,
/// 未登录时返回 null(由调用方决定是否回退到 MockData.currentUser)。
final currentAuthUserProvider = Provider<AppUser?>((ref) {
  final auth = ref.watch(authNotifierProvider);
  return auth.session?.user;
});

/// 当前角色(快捷访问)。
final currentUserRoleProvider = Provider<UserRole?>((ref) {
  return ref.watch(currentAuthUserProvider)?.role;
});

/// 是否已认证。
final isAuthenticatedProvider = Provider<bool>((ref) {
  return ref.watch(authNotifierProvider).isAuthenticated;
});
