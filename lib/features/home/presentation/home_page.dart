import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/providers/app_providers.dart';
import '../../../core/utils/date_utils.dart';
import '../../../core/widgets/state_views.dart';
import '../../../core/widgets/staggered_enter.dart';
import 'widgets/counselor_greeting_section.dart';
import 'widgets/greeting_header.dart';
import 'widgets/latest_notice_section.dart';
import 'widgets/quick_action_section.dart';
import 'widgets/study_summary_section.dart';
import 'widgets/today_progress_section.dart';
import 'widgets/urgent_task_section.dart';

/// 首页 — 概览仪表盘风格。
///
/// 组合多个 section widget:
/// - [GreetingHeader] 顶部问候
/// - [TodayProgressSection] 今日概览英雄卡片
/// - [QuickActionSection] 快捷入口
/// - [CounselorGreetingSection] AI 导员入口
/// - [UrgentTaskSection] 即将截止
/// - [LatestNoticeSection] 校园通知
/// - [StudySummarySection] 今日学习
///
/// 各子组件位于 widgets/ 目录,本文件仅负责编排。
class HomePage extends ConsumerWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final now = DateTime.now();
    final user = ref.watch(currentUserProvider);
    final todayProgress = ref.watch(todayProgressProvider);
    final nearest = ref.watch(nearestDeadlineTaskProvider);
    final unread = ref.watch(unreadNoticeCountProvider);
    final todayTotal = ref.watch(todayStudyTotalProvider);
    final todayTasks = ref.watch(todayTasksProvider);
    final reduceMotion = ref.watch(reduceMotionProvider);
    final greeting = AppDateUtils.greeting(now);

    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async =>
              await Future.delayed(const Duration(milliseconds: 600)),
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              // ===== 顶部问候区 =====
              SliverToBoxAdapter(
                child: StaggeredEnter(
                  child: GreetingHeader(
                    greeting: greeting,
                    name: user.nickname,
                    date: now,
                    unread: unread,
                  ),
                ),
              ),
              const SliverToBoxAdapter(child: SizedBox(height: 12)),

              // ===== 今日概览(英雄卡片) =====
              SliverToBoxAdapter(
                child: StaggeredEnter(
                  delay: const Duration(milliseconds: 60),
                  child: TodayProgressSection(
                    progress: todayProgress,
                    nearest: nearest,
                    todayTaskCount: todayTasks.length,
                  ),
                ),
              ),
              const SliverToBoxAdapter(child: SizedBox(height: 20)),

              // ===== 快捷入口 =====
              const SliverToBoxAdapter(
                child: StaggeredEnter(
                  delay: Duration(milliseconds: 120),
                  child: QuickActionSection(),
                ),
              ),
              const SliverToBoxAdapter(child: SizedBox(height: 20)),

              // ===== AI 导员问候 =====
              const SliverToBoxAdapter(
                child: StaggeredEnter(
                  delay: Duration(milliseconds: 180),
                  child: CounselorGreetingSection(),
                ),
              ),
              const SliverToBoxAdapter(child: SizedBox(height: 20)),

              // ===== 即将截止任务 =====
              const SliverToBoxAdapter(
                child: StaggeredEnter(
                  delay: Duration(milliseconds: 240),
                  child: UrgentTaskSection(),
                ),
              ),
              const SliverToBoxAdapter(child: SizedBox(height: 20)),

              // ===== 最新通知(横向滑动) =====
              const SliverToBoxAdapter(
                child: StaggeredEnter(
                  delay: Duration(milliseconds: 360),
                  child: LatestNoticeSection(),
                ),
              ),
              const SliverToBoxAdapter(child: SizedBox(height: 20)),

              // ===== 学习时长概览 =====
              SliverToBoxAdapter(
                child: StaggeredEnter(
                  delay: const Duration(milliseconds: 480),
                  child: StudySummarySection(
                    todayTotal: todayTotal.valueOrNull,
                    reduceMotion: reduceMotion,
                  ),
                ),
              ),
              const SliverToBoxAdapter(child: SizedBox(height: 24)),
            ],
          ),
        ),
      ),
    );
  }
}
