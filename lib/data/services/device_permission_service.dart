import 'package:permission_handler/permission_handler.dart' as ph;

import 'service_interfaces.dart';

/// 真实权限服务 — 基于 `permission_handler` 插件。
///
/// 实现策略(对齐 AGENTS.md §2.3 "不反复弹窗"):
/// - [requestCamera]: 仅在用户主动点击"开启"时调用,不自动触发
/// - [cameraPermissionStatus]: 不弹窗,基于系统缓存
///   - `permanentlyDenied`: UI 引导用户去系统设置(不调用 requestCamera)
///   - `denied`: 可由用户主动触发再次询问
///   - `notDetermined`: 首次询问
///   - `granted`: 已授权
/// - [openAppSettings]: 跳转系统设置(永久拒绝后引导)
///
/// 平台支持:
/// - Android / iOS: 完整支持
/// - Web: 摄像头权限通过浏览器原生 API,permission_handler 返回 granted/denied
/// - Windows / macOS: 部分支持(取决于 permission_handler 实现)
class DevicePermissionService implements PermissionService {
  @override
  Future<bool> requestCamera() async {
    final status = await ph.Permission.camera.request();
    return status.isGranted;
  }

  @override
  Future<bool> requestNotifications() async {
    // Android 13+ 需请求 POST_NOTIFICATIONS;iOS 需请求 alert/badge/sound
    final status = await ph.Permission.notification.request();
    return status.isGranted;
  }

  @override
  Future<bool> get hasCamera async {
    final status = await ph.Permission.camera.status;
    return status.isGranted;
  }

  @override
  Future<bool> get hasNotifications async {
    final status = await ph.Permission.notification.status;
    return status.isGranted;
  }

  @override
  Future<PermissionStatus> get cameraPermissionStatus async {
    final status = await ph.Permission.camera.status;
    return _mapStatus(status);
  }

  @override
  Future<PermissionStatus> get notificationPermissionStatus async {
    final status = await ph.Permission.notification.status;
    return _mapStatus(status);
  }

  @override
  Future<void> openAppSettings() => ph.openAppSettings();

  /// 将 `permission_handler` 的状态映射到本项目解耦的 [PermissionStatus]。
  ///
  /// 解耦原因:避免 UI 层与 `permission_handler` 包直接耦合,
  /// 便于测试时注入 [MockPermissionService]。
  static PermissionStatus _mapStatus(ph.PermissionStatus status) {
    if (status.isGranted) return PermissionStatus.granted;
    if (status.isPermanentlyDenied) {
      return PermissionStatus.permanentlyDenied;
    }
    if (status.isDenied) return PermissionStatus.denied;
    if (status.isRestricted || status.isLimited) {
      // 受限/部分授权视为已授权(部分功能可用)
      return PermissionStatus.granted;
    }
    return PermissionStatus.notDetermined;
  }
}
