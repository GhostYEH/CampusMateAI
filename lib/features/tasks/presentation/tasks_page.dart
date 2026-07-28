import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/utils/date_utils.dart';
import '../../../core/widgets/cards.dart';
import '../../../core/widgets/state_views.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../data/models/task.dart';
import '../../../data/services/api/api_client.dart';

/// 待办主页面 — Tab 切换 + 搜索 + 类别筛选 + 日历视图。
class TasksPage extends ConsumerStatefulWidget {
  const TasksPage({super.key});

  @override
  ConsumerState<TasksPage> createState() => _TasksPageState();
}

class _TasksPageState extends ConsumerState<TasksPage>
    with TickerProviderStateMixin {
  late final TabController _tabController;
  final TextEditingController _searchController = TextEditingController();
  final FocusNode _searchFocus = FocusNode();

  bool _searchExpanded = false;
  bool _showCalendar = false;
  TaskCategory? _categoryFilter; // null = 全部
  DateTime? _selectedDay; // 日历视图选中的日期

  static const List<_TabSpec> _tabs = [
    _TabSpec(label: '今日'),
    _TabSpec(label: '即将截止'),
    _TabSpec(label: '已完成'),
    _TabSpec(label: '全部'),
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _tabs.length, vsync: this);
    _searchController.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _tabController.dispose();
    _searchController.dispose();
    _searchFocus.dispose();
    super.dispose();
  }

  /// 按搜索词 + 类别过滤,然后排序(截止升序,未截止在前,已完成在后)。
  List<Task> _filteredTasks(List<Task> source) {
    final q = _searchController.text.trim().toLowerCase();
    var list = source;
    if (q.isNotEmpty) {
      list = list.where((t) => t.title.toLowerCase().contains(q)).toList();
    }
    if (_categoryFilter != null) {
      list = list.where((t) => t.category == _categoryFilter).toList();
    }
    return _sortTasks(list);
  }

  List<Task> _sortTasks(List<Task> list) {
    list.sort((a, b) {
      if (a.completed != b.completed) return a.completed ? 1 : -1;
      final ad = a.deadline;
      final bd = b.deadline;
      if (ad == null && bd == null) {
        return a.createdAt.compareTo(b.createdAt);
      }
      if (ad == null) return 1;
      if (bd == null) return -1;
      return ad.compareTo(bd);
    });
    return list;
  }

  void _toggleComplete(Task task) {
    final wasCompleted = task.completed;
    // 异步调用后端,失败时显示错误(对齐 Flutter 要求 #8:不静默伪装成功)
    ref.read(taskListProvider.notifier).toggleComplete(task).catchError((e) {
      if (!mounted) return;
      _showErrorSnack(e is ApiException ? e.message : '操作失败,请重试');
    });
    if (!mounted) return;
    if (!wasCompleted) {
      ScaffoldMessenger.of(context).hideCurrentSnackBar();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text('已完成 ✓'),
          duration: const Duration(seconds: 5),
          action: SnackBarAction(
            label: '撤销',
            onPressed: () {
              ref
                  .read(taskListProvider.notifier)
                  .updateTask(
                    task.copyWith(completed: false, completedAt: null),
                  )
                  .catchError((e) {
                if (!mounted) return;
                _showErrorSnack(e is ApiException ? e.message : '撤销失败,请重试');
              });
            },
          ),
        ),
      );
    }
  }

  void _softDelete(Task task) {
    ref.read(taskListProvider.notifier).softDelete(task.id).catchError((e) {
      if (!mounted) return;
      _showErrorSnack(e is ApiException ? e.message : '删除失败,请重试');
    });
    if (!mounted) return;
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('已删除「${task.title}」'),
        duration: const Duration(seconds: 5),
        action: SnackBarAction(
          label: '撤销',
          onPressed: () {
            ref
                .read(taskListProvider.notifier)
                .restore(task.id)
                .catchError((e) {
              if (!mounted) return;
              _showErrorSnack(e is ApiException ? e.message : '恢复失败,请重试');
            });
          },
        ),
      ),
    );
  }

  void _showErrorSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        backgroundColor: AppColors.danger,
        content: Row(
          children: [
            const Icon(
              Icons.error_outline_rounded,
              color: AppColors.onPrimary,
              size: 18,
            ),
            const SizedBox(width: 8),
            Expanded(child: Text(message)),
          ],
        ),
      ),
    );
  }

  /// 跳转到 AI 导员,携带当前用户的真实最近待办(对齐要求 #4)。
  ///
  /// 仅发送必要字段(id/title/deadline/priority/status),后端会重新校验归属。
  /// 若当前没有任何待办,仍然跳转(只是不携带 recent_tasks)。
  void _askCounselorWithTasks() {
    final upcoming = ref.read(upcomingTasksProvider);
    final recentTasks = upcoming.take(5).map((t) {
      return {
        'id': t.id,
        'title': t.title,
        'deadline': t.deadline?.toIso8601String(),
        'priority': t.priority.name,
        'status': t.completed ? 'completed' : 'pending',
      };
    }).toList(growable: false);
    context.go(
      '/counselor',
      extra: <String, dynamic>{
        'context_title': recentTasks.isEmpty ? '我的待办' : '我的最近待办',
        'recent_tasks': recentTasks,
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final todayTasks = ref.watch(todayTasksProvider);
    final upcomingTasks = ref.watch(upcomingTasksProvider);
    final completedTasks = ref.watch(completedTasksProvider);
    final allTasks =
        ref.watch(taskListProvider).where((t) => !t.deleted).toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('待办'),
        actions: [
          IconButton(
            icon: const Icon(Icons.support_agent_rounded),
            tooltip: '问 AI 导员',
            onPressed: _askCounselorWithTasks,
          ),
          IconButton(
            icon: Icon(
              _searchExpanded ? Icons.search_off_rounded : Icons.search_rounded,
            ),
            tooltip: '搜索',
            onPressed: () {
              setState(() {
                _searchExpanded = !_searchExpanded;
                if (!_searchExpanded) {
                  _searchController.clear();
                  _searchFocus.unfocus();
                }
              });
            },
          ),
          IconButton(
            icon: Icon(
              _showCalendar
                  ? Icons.view_list_rounded
                  : Icons.calendar_month_rounded,
            ),
            tooltip: _showCalendar ? '切换到列表' : '切换到日历',
            onPressed: () => setState(() => _showCalendar = !_showCalendar),
          ),
          const SizedBox(width: 4),
        ],
        bottom: _showCalendar
            ? null
            : TabBar(
                controller: _tabController,
                isScrollable: false,
                tabs: [for (final t in _tabs) Tab(text: t.label)],
              ),
      ),
      body: Column(
        children: [
          if (_searchExpanded && !_showCalendar) _searchBar(),
          if (_showCalendar) _calendarView(allTasks),
          if (!_showCalendar) _categoryChips(),
          Expanded(
            child: _showCalendar
                ? _dayTasksView(allTasks)
                : TabBarView(
                    controller: _tabController,
                    children: [
                      _listBody(_filteredTasks(todayTasks)),
                      _listBody(_filteredTasks(upcomingTasks)),
                      _listBody(_filteredTasks(completedTasks)),
                      _listBody(_filteredTasks(allTasks)),
                    ],
                  ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => context.push('/tasks/create'),
        tooltip: '新建待办',
        child: const Icon(Icons.add_rounded),
      ),
    );
  }

  Widget _searchBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.edge,
        4,
        AppSpacing.edge,
        8,
      ),
      child: TextField(
        controller: _searchController,
        focusNode: _searchFocus,
        autofocus: true,
        decoration: InputDecoration(
          hintText: '搜索任务标题',
          prefixIcon: const Icon(Icons.search_rounded, size: 20),
          suffixIcon: _searchController.text.isNotEmpty
              ? IconButton(
                  icon: const Icon(Icons.close_rounded, size: 18),
                  onPressed: _searchController.clear,
                )
              : null,
          isDense: true,
        ),
      ),
    );
  }

  Widget _categoryChips() {
    final categories = <TaskCategory?>[null, ...TaskCategory.values];
    return SizedBox(
      height: 44,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.edge,
          vertical: 6,
        ),
        itemCount: categories.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final cat = categories[index];
          final selected = _categoryFilter == cat;
          final label = cat == null ? '全部' : cat.displayName;
          return GestureDetector(
            onTap: () => setState(() => _categoryFilter = cat),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
              decoration: BoxDecoration(
                color: selected ? AppColors.primary : AppColors.bgSunken,
                borderRadius: BorderRadius.circular(999),
                border: Border.all(
                  color: selected ? AppColors.primary : Colors.transparent,
                  width: 0.8,
                ),
              ),
              child: Center(
                child: Text(
                  label,
                  style: AppTypography.label.copyWith(
                    color: selected
                        ? AppColors.onPrimary
                        : AppColors.textSecondary,
                    fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _calendarView(List<Task> allTasks) {
    final now = DateTime.now();
    final firstOfMonth = DateTime(now.year, now.month, 1);
    final daysInMonth = DateTime(now.year, now.month + 1, 0).day;
    final firstWeekday = (firstOfMonth.weekday - 1) % 7;

    final daysWithTasks = <int>{};
    for (final t in allTasks) {
      final d = t.deadline;
      if (d != null && d.year == now.year && d.month == now.month) {
        daysWithTasks.add(d.day);
      }
    }

    return Container(
      margin: const EdgeInsets.fromLTRB(
        AppSpacing.edge,
        8,
        AppSpacing.edge,
        4,
      ),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.bgSurface,
        borderRadius: BorderRadius.circular(AppRadius.md),
        border: Border.all(color: AppColors.border, width: 0.8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                '${now.year}年${now.month}月',
                style: AppTypography.subtitle,
              ),
              const Spacer(),
              Text(
                '共 ${daysWithTasks.length} 天有任务',
                style: AppTypography.caption,
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: ['一', '二', '三', '四', '五', '六', '日'].map((w) {
              return Expanded(
                child: Center(
                  child: Text(
                    w,
                    style: AppTypography.label.copyWith(
                      color: AppColors.textTertiary,
                      fontSize: 11,
                    ),
                  ),
                ),
              );
            }).toList(),
          ),
          const SizedBox(height: 6),
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 7,
              mainAxisSpacing: 4,
              crossAxisSpacing: 0,
              childAspectRatio: 1,
            ),
            itemCount: firstWeekday + daysInMonth,
            itemBuilder: (context, index) {
              if (index < firstWeekday) return const SizedBox.shrink();
              final day = index - firstWeekday + 1;
              final isToday = day == now.day;
              final isSelected = _selectedDay != null &&
                  _selectedDay!.year == now.year &&
                  _selectedDay!.month == now.month &&
                  _selectedDay!.day == day;
              final hasTask = daysWithTasks.contains(day);
              return GestureDetector(
                onTap: () {
                  setState(() {
                    _selectedDay =
                        isSelected ? null : DateTime(now.year, now.month, day);
                  });
                },
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: isSelected
                        ? AppColors.primary
                        : isToday
                            ? AppColors.primarySubtle
                            : Colors.transparent,
                    shape: BoxShape.circle,
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        '$day',
                        style: AppTypography.body.copyWith(
                          color: isSelected
                              ? AppColors.onPrimary
                              : isToday
                                  ? AppColors.primary
                                  : AppColors.textPrimary,
                          fontWeight: isToday || isSelected
                              ? FontWeight.w700
                              : FontWeight.w400,
                          fontSize: 13,
                        ),
                      ),
                      if (hasTask)
                        Container(
                          width: 4,
                          height: 4,
                          margin: const EdgeInsets.only(top: 2),
                          decoration: BoxDecoration(
                            color: isSelected
                                ? AppColors.onPrimary
                                : AppColors.primary,
                            shape: BoxShape.circle,
                          ),
                        ),
                    ],
                  ),
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _dayTasksView(List<Task> allTasks) {
    if (_selectedDay == null) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.event_available_rounded,
                size: 36,
                color: AppColors.textTertiary,
              ),
              SizedBox(height: 12),
              Text(
                '点击有圆点的日期查看当日任务',
                style: AppTypography.caption,
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      );
    }
    final dayTasks = allTasks.where((t) {
      if (t.deadline == null) return false;
      return AppDateUtils.isSameDay(t.deadline!, _selectedDay!);
    }).toList();
    if (dayTasks.isEmpty) {
      return EmptyStateView(
        icon: Icons.event_available_rounded,
        title: '该日暂无任务',
        message: AppDateUtils.formatDate(_selectedDay!),
      );
    }
    return _listBody(_sortTasks(dayTasks));
  }

  Widget _listBody(List<Task> tasks) {
    if (tasks.isEmpty) {
      return EmptyStateView(
        icon: Icons.checklist_rounded,
        title: '暂无任务',
        message: '点击右下角 + 新建一项待办',
        actionLabel: '新建任务',
        onAction: () => context.push('/tasks/create'),
      );
    }
    return StaggeredListView(
      itemCount: tasks.length,
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.edge,
        8,
        AppSpacing.edge,
        88,
      ),
      separator: const SizedBox(height: 10),
      itemBuilder: (context, index) {
        final task = tasks[index];
        return Dismissible(
          key: ValueKey(task.id),
          background: _dismissibleBackground(
            Alignment.centerLeft,
            AppColors.success,
            Icons.check_rounded,
            task.completed ? '取消完成' : '完成',
          ),
          secondaryBackground: _dismissibleBackground(
            Alignment.centerRight,
            AppColors.danger,
            Icons.delete_outline_rounded,
            '删除',
          ),
          direction: DismissDirection.horizontal,
          confirmDismiss: (direction) async {
            if (direction == DismissDirection.startToEnd) {
              _toggleComplete(task);
            } else {
              _softDelete(task);
            }
            return false; // 不真删除,由数据驱动 UI
          },
          child: TaskCard(
            task: task,
            onToggle: () => _toggleComplete(task),
          ),
        );
      },
    );
  }

  Widget _dismissibleBackground(
    Alignment alignment,
    Color color,
    IconData icon,
    String label,
  ) {
    return Container(
      alignment: alignment,
      padding: const EdgeInsets.symmetric(horizontal: 20),
      color: color.withValues(alpha: 0.10),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 6),
          Text(
            label,
            style: AppTypography.bodyStrong.copyWith(color: color),
          ),
        ],
      ),
    );
  }
}

class _TabSpec {
  const _TabSpec({required this.label});
  final String label;
}
