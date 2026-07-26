import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/storage/data_persistence_service.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../data/models/knowledge.dart';
import 'widgets/backend_status_card.dart';

/// 个人中心页 — 用户设置与数据管理。
///
/// 设计原则(遵循 AGENTS.md §2):
/// - 不暴露"演示模式"、"Mock 切换"、"恢复演示数据"等入口
/// - 所有数据管理操作仅影响本地缓存,不影响真实后端数据
/// - 后端断开时显示"服务暂时不可用",不自动切换到 Mock
class ProfilePage extends ConsumerWidget {
  const ProfilePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentAuthUserProvider);
    final settings = ref.watch(appSettingsProvider);

    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.edge,
            vertical: 8,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              StaggeredEnter(
                child: _ProfileHeader(user: user),
              ),
              const SizedBox(height: 16),
              StaggeredEnter(
                delay: const Duration(milliseconds: 60),
                child: _SettingsGroup(
                  title: '通知与提醒',
                  children: [
                    _SwitchTile(
                      icon: Icons.notifications_active_outlined,
                      label: '通知来源',
                      subtitle: '接收校园通知整理',
                      value: settings.notificationSourcesEnabled,
                      onChanged: (_) {},
                    ),
                    _SwitchTile(
                      icon: Icons.alarm_rounded,
                      label: '任务提醒',
                      subtitle: '截止前 ${settings.reminderLeadMinutes} 分钟提醒',
                      value: settings.reminderEnabled,
                      onChanged: (_) => ref
                          .read(appSettingsProvider.notifier)
                          .toggleReminder(),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              const StaggeredEnter(
                delay: Duration(milliseconds: 120),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Padding(
                      padding: EdgeInsets.only(left: 4, bottom: 8),
                      child: Text('后端连接', style: AppTypography.label),
                    ),
                    BackendStatusCard(),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              StaggeredEnter(
                delay: const Duration(milliseconds: 180),
                child: _SettingsGroup(
                  title: 'AI 导员',
                  children: [
                    _SwitchTile(
                      icon: Icons.smart_toy_outlined,
                      label: '主动建议',
                      subtitle: '根据待办主动提醒',
                      value: settings.counselorProactiveSuggestion,
                      onChanged: (_) => ref
                          .read(appSettingsProvider.notifier)
                          .toggleProactiveSuggestion(),
                    ),
                    _ActionTile(
                      icon: Icons.menu_book_rounded,
                      label: '知识库管理',
                      subtitle: '查看状态、上传/删除文档、重建索引',
                      onTap: () => context.push('/knowledge'),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              StaggeredEnter(
                delay: const Duration(milliseconds: 240),
                child: _SettingsGroup(
                  title: '学习与表情识别',
                  children: [
                    _SwitchTile(
                      icon: Icons.camera_alt_outlined,
                      label: '摄像头权限',
                      subtitle:
                          settings.cameraPermissionGranted ? '已授权' : '未授权',
                      value: settings.cameraPermissionGranted,
                      onChanged: (_) async {
                        final granted = await ref
                            .read(permissionServiceProvider)
                            .requestCamera();
                        if (granted) {
                          ref
                              .read(appSettingsProvider.notifier)
                              .grantCameraPermission();
                        }
                      },
                    ),
                    _SwitchTile(
                      icon: Icons.face_retouching_natural_outlined,
                      label: '表情识别',
                      subtitle: '本地识别 · 不作心理诊断',
                      value: settings.expressionRecognitionEnabled,
                      onChanged: (_) => ref
                          .read(appSettingsProvider.notifier)
                          .toggleExpressionRecognition(),
                    ),
                    _InfoTile(
                      icon: Icons.memory_rounded,
                      label: '模型版本',
                      value: settings.modelVersion,
                    ),
                    _InfoTile(
                      icon: Icons.timer_outlined,
                      label: '休息提醒间隔',
                      value: '${settings.studyRestIntervalMinutes} 分钟',
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              StaggeredEnter(
                delay: const Duration(milliseconds: 300),
                child: _SettingsGroup(
                  title: '外观与无障碍',
                  children: [
                    _SwitchTile(
                      icon: Icons.dark_mode_outlined,
                      label: '深色模式',
                      value: settings.darkMode,
                      onChanged: (_) => ref
                          .read(appSettingsProvider.notifier)
                          .toggleDarkMode(),
                    ),
                    _SwitchTile(
                      icon: Icons.animation_outlined,
                      label: '减少动态效果',
                      subtitle: '关闭进入动画与过渡',
                      value: settings.reduceMotion,
                      onChanged: (_) => ref
                          .read(appSettingsProvider.notifier)
                          .toggleReduceMotion(),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              StaggeredEnter(
                delay: const Duration(milliseconds: 360),
                child: _SettingsGroup(
                  title: '本地数据管理',
                  children: [
                    _ActionTile(
                      icon: Icons.cleaning_services_rounded,
                      label: '清除聊天记录',
                      subtitle: '删除 AI 导员的历史对话(仅本地)',
                      onTap: () => _confirmClearChat(context, ref),
                    ),
                    _ActionTile(
                      icon: Icons.checklist_rtl_rounded,
                      label: '清除本地待办',
                      subtitle: '删除本地所有待办任务(不影响后端)',
                      onTap: () => _confirmClearTasks(context, ref),
                    ),
                    _ActionTile(
                      icon: Icons.folder_delete_outlined,
                      label: '删除用户导入的知识库文档',
                      subtitle: '仅删除你导入的文档,保留校园公共资料',
                      onTap: () => _confirmDeleteUserDocuments(context, ref),
                    ),
                    _ActionTile(
                      icon: Icons.delete_outline_rounded,
                      label: '清除所有本地数据',
                      subtitle: '清除本地待办、学习记录与设置',
                      iconColor: AppColors.danger,
                      onTap: () => _confirmClear(context, ref),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              StaggeredEnter(
                delay: const Duration(milliseconds: 420),
                child: _SettingsGroup(
                  title: '关于',
                  children: [
                    _ActionTile(
                      icon: Icons.info_outline_rounded,
                      label: '关于项目',
                      onTap: () => _showAbout(context),
                    ),
                    _ActionTile(
                      icon: Icons.privacy_tip_outlined,
                      label: '隐私政策',
                      onTap: () => _showPrivacy(context),
                    ),
                    _ActionTile(
                      icon: Icons.feedback_outlined,
                      label: '意见反馈',
                      onTap: () => _showFeedback(context),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              StaggeredEnter(
                delay: const Duration(milliseconds: 480),
                child: _SignOutTile(
                  onTap: () => _confirmSignOut(context, ref),
                ),
              ),
              const SizedBox(height: 24),
              Center(
                child: Text(
                  '校园事务智能陪伴助手 · v0.1.0\n计算机设计大赛参赛作品',
                  style: AppTypography.overline.copyWith(fontSize: 10.5),
                  textAlign: TextAlign.center,
                ),
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }

  void _confirmClear(BuildContext context, WidgetRef ref) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('清除本地数据'),
        content: const Text('将清除本地待办、学习记录与设置,且不可恢复。'
            '此操作不影响后端已保存的课程、通知与任务数据。确定继续吗?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppColors.danger),
            onPressed: () async {
              Navigator.pop(context);
              await ref.read(dataPersistenceProvider).clearAllData();
              ref.read(appSettingsProvider.notifier).resetToDefault();
              ref.read(chatMessagesProvider.notifier).clear();
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('本地数据已清除')),
                );
              }
            },
            child: const Text('清除'),
          ),
        ],
      ),
    );
  }

  /// 清除聊天记录 — 仅影响本地对话,不影响待办或知识库。
  void _confirmClearChat(BuildContext context, WidgetRef ref) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('清除聊天记录'),
        content: const Text('将删除 AI 导员的所有历史对话。\n\n'
            '影响范围:仅本地对话记录。\n'
            '不影响:待办任务、知识库文档、后端数据。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () {
              Navigator.pop(context);
              ref.read(chatMessagesProvider.notifier).clear();
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('聊天记录已清除')),
                );
              }
            },
            child: const Text('清除'),
          ),
        ],
      ),
    );
  }

  /// 清除本地待办 — 仅影响本地任务,不影响知识库或后端。
  void _confirmClearTasks(BuildContext context, WidgetRef ref) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('清除本地待办'),
        content: const Text('将删除本地所有待办任务。\n\n'
            '影响范围:本地待办、提醒设置。\n'
            '不影响:聊天记录、知识库文档、后端数据。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppColors.danger),
            onPressed: () async {
              Navigator.pop(context);
              await ref.read(taskRepositoryProvider).clearAll();
              await ref.read(dataPersistenceProvider).saveTasks();
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('本地待办已清除')),
                );
              }
            },
            child: const Text('清除'),
          ),
        ],
      ),
    );
  }

  /// 删除用户导入的知识库文档 — 仅删除用户文档,保留校园公共资料。
  void _confirmDeleteUserDocuments(BuildContext context, WidgetRef ref) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('删除用户导入的知识库文档'),
        content: const Text('将删除所有你导入的知识库文档,保留校园公共资料。\n\n'
            '影响范围:仅你导入的文档。\n'
            '不影响:待办任务、聊天记录、后端数据。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppColors.danger),
            onPressed: () async {
              Navigator.pop(context);
              try {
                final result = await ref
                    .read(knowledgeManagementProvider)
                    .manageData(DataManagementAction.deleteUserDocuments);
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text(result.message)),
                  );
                }
              } catch (e) {
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('删除失败:$e')),
                  );
                }
              }
            },
            child: const Text('删除'),
          ),
        ],
      ),
    );
  }

  void _confirmSignOut(BuildContext context, WidgetRef ref) {
    showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('退出登录'),
        content: const Text('将退出当前账号,需要重新登录才能继续使用。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('取消'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppColors.danger),
            onPressed: () async {
              Navigator.pop(dialogContext);
              await ref.read(authNotifierProvider.notifier).logout();
            },
            child: const Text('退出'),
          ),
        ],
      ),
    );
  }

  void _showAbout(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('关于项目'),
        content: const Text(
          '校园事务智能陪伴助手\n\n'
          '面向大学生的智能陪伴应用,集成校园通知整理、待办管理、'
          'AI导员问答、基于CNN的面部表情识别与学习陪伴。\n\n'
          '支持学生、教师、管理员多角色协作,'
          '连接真实 FastAPI 后端服务。',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('知道了'),
          ),
        ],
      ),
    );
  }

  void _showPrivacy(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('隐私政策'),
        content: const Text(
          '• 表情识别在本地进行,不上传图像。\n'
          '• 仅识别可观察表情,不进行心理诊断。\n'
          '• 本地数据保存在设备,可随时清除。\n'
          '• 不收集、不共享个人敏感信息。\n'
          '• 密码不存储在本地,token 经过混淆保存。',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('知道了'),
          ),
        ],
      ),
    );
  }

  void _showFeedback(BuildContext context) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('感谢反馈!暂未接入反馈通道。')),
    );
  }
}

class _ProfileHeader extends StatelessWidget {
  const _ProfileHeader({required this.user});
  final dynamic user;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final displayName = (user?.name as String?) ?? '未登录';
    final college = (user?.college as String?) ?? '';
    final grade = (user?.grade as String?) ?? '';
    final studentId = (user?.studentId as String?) ?? '';
    return AppCard(
      padding: const EdgeInsets.all(20),
      child: Row(
        children: [
          Container(
            width: 60,
            height: 60,
            decoration: BoxDecoration(
              color: c.primary,
              shape: BoxShape.circle,
            ),
            child: Center(
              child: Text(
                displayName.isNotEmpty ? displayName.characters.first : '?',
                style: TextStyle(
                  color: c.onPrimary,
                  fontSize: 26,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(displayName, style: AppTypography.headline),
                if (college.isNotEmpty || grade.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(
                    [college, grade].where((s) => s.isNotEmpty).join(' · '),
                    style: AppTypography.caption,
                  ),
                ],
                if (studentId.isNotEmpty) ...[
                  const SizedBox(height: 2),
                  Text('学号/工号 $studentId', style: AppTypography.overline),
                ],
              ],
            ),
          ),
          Icon(
            Icons.chevron_right_rounded,
            color: c.textTertiary,
          ),
        ],
      ),
    );
  }
}

class _SettingsGroup extends StatelessWidget {
  const _SettingsGroup({required this.title, required this.children});
  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 8),
          child: Text(title, style: AppTypography.label),
        ),
        AppCard(
          padding: EdgeInsets.zero,
          child: Column(
            children: [
              for (int i = 0; i < children.length; i++) ...[
                children[i],
                if (i != children.length - 1)
                  const Divider(height: 1, indent: 56),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _SwitchTile extends StatelessWidget {
  const _SwitchTile({
    required this.icon,
    required this.label,
    required this.value,
    required this.onChanged,
    this.subtitle,
  });

  final IconData icon;
  final String label;
  final String? subtitle;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Row(
        children: [
          Icon(icon, size: 20, color: c.textSecondary),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: AppTypography.body),
                if (subtitle != null)
                  Text(subtitle!, style: AppTypography.caption),
              ],
            ),
          ),
          Switch(value: value, onChanged: onChanged),
        ],
      ),
    );
  }
}

class _InfoTile extends StatelessWidget {
  const _InfoTile({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          Icon(icon, size: 20, color: c.textSecondary),
          const SizedBox(width: 12),
          Expanded(child: Text(label, style: AppTypography.body)),
          Text(value, style: AppTypography.caption),
        ],
      ),
    );
  }
}

class _ActionTile extends StatelessWidget {
  const _ActionTile({
    required this.icon,
    required this.label,
    required this.onTap,
    this.subtitle,
    this.iconColor = AppColors.textSecondary,
  });

  final IconData icon;
  final String label;
  final String? subtitle;
  final VoidCallback onTap;
  final Color iconColor;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final isDanger = iconColor == AppColors.danger;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          child: Row(
            children: [
              Icon(icon, size: 20, color: iconColor),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      label,
                      style: AppTypography.body.copyWith(
                        color: isDanger ? c.danger : c.textPrimary,
                      ),
                    ),
                    if (subtitle != null)
                      Text(subtitle!, style: AppTypography.caption),
                  ],
                ),
              ),
              Icon(
                Icons.chevron_right_rounded,
                size: 18,
                color: c.textTertiary,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SignOutTile extends StatelessWidget {
  const _SignOutTile({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return AppCard(
      padding: EdgeInsets.zero,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(AppRadius.md),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            child: Row(
              children: [
                Icon(
                  Icons.logout_rounded,
                  size: 20,
                  color: c.danger,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    '退出登录',
                    style: AppTypography.body.copyWith(color: c.danger),
                  ),
                ),
                Icon(
                  Icons.chevron_right_rounded,
                  size: 18,
                  color: c.textTertiary,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
