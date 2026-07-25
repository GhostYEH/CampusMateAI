import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/staggered_enter.dart';

class ProfilePage extends ConsumerWidget {
  const ProfilePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
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
              StaggeredEnter(
                delay: const Duration(milliseconds: 120),
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
                    const _InfoTile(
                      icon: Icons.school_outlined,
                      label: '知识库',
                      value: '模拟资料来源',
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              StaggeredEnter(
                delay: const Duration(milliseconds: 180),
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
                delay: const Duration(milliseconds: 240),
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
                delay: const Duration(milliseconds: 300),
                child: _SettingsGroup(
                  title: '演示与数据',
                  children: [
                    _SwitchTile(
                      icon: Icons.play_circle_outline_rounded,
                      label: '比赛演示模式',
                      subtitle: '开启完整演示数据链路',
                      value: settings.demoMode,
                      onChanged: (_) => ref
                          .read(appSettingsProvider.notifier)
                          .toggleDemoMode(),
                    ),
                    _ActionTile(
                      icon: Icons.delete_outline_rounded,
                      label: '清除本地数据',
                      iconColor: AppColors.danger,
                      onTap: () => _confirmClear(context, ref),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              StaggeredEnter(
                delay: const Duration(milliseconds: 360),
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
        content: const Text('将清除本地待办、聊天记录与学习记录,且不可恢复。确定继续吗?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppColors.danger),
            onPressed: () {
              ref.read(chatMessagesProvider.notifier).clear();
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('本地数据已清除')),
              );
            },
            child: const Text('清除'),
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
          '当前阶段:第一阶段 · 高质量可运行前端原型(Mock 业务闭环)。\n\n'
          '后续:接入 FastAPI + RAG 后端、LiteRT 部署 CNN 模型。',
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
          '• Mock 阶段所有后端、知识库、CNN 均为模拟。',
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
      const SnackBar(content: Text('感谢反馈!Mock 阶段暂未接入反馈通道。')),
    );
  }
}

class _ProfileHeader extends StatelessWidget {
  const _ProfileHeader({required this.user});
  final dynamic user;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(20),
      child: Row(
        children: [
          Container(
            width: 60,
            height: 60,
            decoration: const BoxDecoration(
              color: AppColors.primary,
              shape: BoxShape.circle,
            ),
            child: const Center(
              child: Text(
                '知',
                style: TextStyle(
                  color: AppColors.onPrimary,
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
                Text(user.name, style: AppTypography.headline),
                const SizedBox(height: 4),
                Text(
                  '${user.college} · ${user.grade}',
                  style: AppTypography.caption,
                ),
                const SizedBox(height: 2),
                Text(
                  '学号 ${user.studentId}',
                  style: AppTypography.overline,
                ),
              ],
            ),
          ),
          const Icon(
            Icons.chevron_right_rounded,
            color: AppColors.textTertiary,
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
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Row(
        children: [
          Icon(icon, size: 20, color: AppColors.textSecondary),
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
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          Icon(icon, size: 20, color: AppColors.textSecondary),
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
    this.iconColor = AppColors.textSecondary,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final Color iconColor;

  @override
  Widget build(BuildContext context) {
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
                child: Text(
                  label,
                  style: AppTypography.body.copyWith(
                    color: iconColor == AppColors.danger
                        ? AppColors.danger
                        : AppColors.textPrimary,
                  ),
                ),
              ),
              const Icon(
                Icons.chevron_right_rounded,
                size: 18,
                color: AppColors.textTertiary,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
