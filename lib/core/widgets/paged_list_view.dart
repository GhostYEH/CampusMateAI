import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/design_system/app_colors.dart';
import '../../app/design_system/app_typography.dart';
import '../../data/models/pagination.dart';
import 'skeleton_loader.dart';
import 'state_views.dart';

/// 分页列表视图 — 统一处理分页加载、空 / 错 / 加载更多状态。
///
/// 性能(AGENTS.md §8.2):
/// - 全部使用 LazyListView,不一次性构建
/// - 滚动到底自动加载下一页
/// - 保留筛选和滚动位置(由 controller 维护)
/// - 避免 shrinkWrap 大列表嵌套
class PagedListView<T> extends ConsumerStatefulWidget {
  const PagedListView({
    super.key,
    required this.fetchPage,
    required this.itemBuilder,
    this.separator,
    this.padding,
    this.scrollController,
    this.shrinkWrap = false,
    this.physics,
    this.pageSize = 20,
    this.emptyIcon,
    this.emptyTitle,
    this.emptyMessage,
    this.emptyActionLabel,
    this.onEmptyAction,
    this.errorBuilder,
    this.header,
    this.footer,
    this.enablePullToRefresh = true,
    this.onRefresh,
  });

  /// 获取一页数据。page 从 1 开始。
  final Future<PaginatedResult<T>> Function(int page, int pageSize) fetchPage;

  /// 构建单项。
  final Widget Function(BuildContext, T, int index) itemBuilder;

  /// 分隔符(可选)。
  final Widget? separator;

  /// 列表内边距。
  final EdgeInsets? padding;

  /// 滚动控制器(用于保留位置)。
  final ScrollController? scrollController;

  /// 是否 shrinkWrap(默认 false — 避免嵌套性能问题)。
  final bool shrinkWrap;

  final ScrollPhysics? physics;
  final int pageSize;

  final IconData? emptyIcon;
  final String? emptyTitle;
  final String? emptyMessage;
  final String? emptyActionLabel;
  final VoidCallback? onEmptyAction;

  /// 自定义错误视图(默认使用 ErrorStateView)。
  final Widget Function(Object error, VoidCallback retry)? errorBuilder;

  /// 列表头部 / 底部(非滚动吸顶,作为 ListRange)。
  final Widget? header;
  final Widget? footer;

  final bool enablePullToRefresh;
  final Future<void> Function()? onRefresh;

  @override
  ConsumerState<PagedListView<T>> createState() => _PagedListViewState<T>();
}

class _PagedListViewState<T> extends ConsumerState<PagedListView<T>> {
  final _items = <T>[];
  final _ownController = ScrollController();
  bool _isLoadingFirst = true;
  bool _isLoadingMore = false;
  bool _hasMore = true;
  Object? _error;
  int _currentPage = 0;

  ScrollController get _controller => widget.scrollController ?? _ownController;

  @override
  void initState() {
    super.initState();
    _loadFirst();
    _controller.addListener(_onScroll);
  }

  @override
  void dispose() {
    _ownController.removeListener(_onScroll);
    _ownController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!_controller.hasClients) return;
    final pos = _controller.position;
    if (pos.pixels >= pos.maxScrollExtent - 240) {
      _loadMore();
    }
  }

  Future<void> _loadFirst() async {
    setState(() {
      _isLoadingFirst = true;
      _error = null;
      _items.clear();
      _currentPage = 0;
      _hasMore = true;
    });
    try {
      final result = await widget.fetchPage(1, widget.pageSize);
      if (!mounted) return;
      setState(() {
        _items
          ..clear()
          ..addAll(result.items);
        _currentPage = 1;
        _hasMore = result.hasMore;
        _isLoadingFirst = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e;
        _isLoadingFirst = false;
      });
    }
  }

  Future<void> _loadMore() async {
    if (_isLoadingMore || _isLoadingFirst || !_hasMore) return;
    setState(() => _isLoadingMore = true);
    try {
      final nextPage = _currentPage + 1;
      final result = await widget.fetchPage(nextPage, widget.pageSize);
      if (!mounted) return;
      setState(() {
        _items.addAll(result.items);
        _currentPage = nextPage;
        _hasMore = result.hasMore;
        _isLoadingMore = false;
      });
    } catch (_) {
      if (!mounted) return;
      // 加载更多失败 — 静默,下次滚动重试
      setState(() => _isLoadingMore = false);
    }
  }

  Future<void> _onRefresh() async {
    if (widget.onRefresh != null) {
      await widget.onRefresh!();
    }
    await _loadFirst();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;

    if (_isLoadingFirst) {
      return _buildSkeleton();
    }

    if (_error != null) {
      final retry = widget.errorBuilder?.call(_error!, _loadFirst) ??
          ErrorStateView(
            message: '加载失败,请重试',
            onRetry: _loadFirst,
          );
      return Center(child: retry);
    }

    if (_items.isEmpty) {
      return Center(
        child: EmptyStateView(
          icon: widget.emptyIcon ?? Icons.inbox_outlined,
          title: widget.emptyTitle ?? '暂无数据',
          message: widget.emptyMessage,
          actionLabel: widget.emptyActionLabel,
          onAction: widget.onEmptyAction,
        ),
      );
    }

    final hasHeader = widget.header != null;
    final itemCount = _items.length + (hasHeader ? 1 : 0) + 1; // +footer

    Widget list = widget.separator != null
        ? ListView.separated(
            controller: _controller,
            padding: widget.padding,
            shrinkWrap: widget.shrinkWrap,
            physics: widget.physics,
            keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
            itemCount: itemCount,
            separatorBuilder: (context, index) {
              // 在 header 与第一项之间、最后一项与 footer 之间不显示分隔符
              final isHeader = hasHeader && index == 0;
              final isFooter = index == itemCount - 1;
              if (isHeader || isFooter) return const SizedBox.shrink();
              return widget.separator!;
            },
            itemBuilder: (context, index) {
              if (hasHeader && index == 0) {
                return KeyedSubtree(
                  key: const ValueKey('paged_header'),
                  child: widget.header!,
                );
              }
              if (index == itemCount - 1) {
                return _buildFooter(c);
              }
              final itemIndex = hasHeader ? index - 1 : index;
              if (itemIndex < 0 || itemIndex >= _items.length) {
                return const SizedBox.shrink();
              }
              return widget.itemBuilder(
                context,
                _items[itemIndex],
                itemIndex,
              );
            },
          )
        : ListView.builder(
            controller: _controller,
            padding: widget.padding,
            shrinkWrap: widget.shrinkWrap,
            physics: widget.physics,
            keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
            itemCount: itemCount,
            itemBuilder: (context, index) {
              if (hasHeader && index == 0) {
                return KeyedSubtree(
                  key: const ValueKey('paged_header'),
                  child: widget.header!,
                );
              }
              if (index == itemCount - 1) {
                return _buildFooter(c);
              }
              final itemIndex = hasHeader ? index - 1 : index;
              if (itemIndex < 0 || itemIndex >= _items.length) {
                return const SizedBox.shrink();
              }
              return widget.itemBuilder(
                context,
                _items[itemIndex],
                itemIndex,
              );
            },
          );

    if (widget.enablePullToRefresh) {
      list = RefreshIndicator(
        onRefresh: _onRefresh,
        child: list,
      );
    }
    return list;
  }

  Widget _buildSkeleton() {
    return ListView.builder(
      physics: const NeverScrollableScrollPhysics(),
      itemCount: 6,
      itemBuilder: (context, index) => const SkeletonListItem(),
    );
  }

  Widget _buildFooter(AppColorScheme c) {
    if (_isLoadingMore) {
      return Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Center(
          child: SizedBox(
            width: 22,
            height: 22,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation(c.primary),
            ),
          ),
        ),
      );
    }
    if (!_hasMore) {
      return Padding(
        padding: const EdgeInsets.symmetric(
          vertical: AppSpacing.md,
        ),
        child: Center(
          child: Text(
            '已加载全部',
            style: AppTypography.overline.copyWith(color: c.textTertiary),
          ),
        ),
      );
    }
    return const SizedBox.shrink();
  }
}

/// 通用 PaginatedResult 数据生成。
class PaginatedResultBuilder<T> {
  PaginatedResultBuilder._();

  static PaginatedResult<T> fromList<T>(
    List<T> allItems,
    PageRequest page,
  ) {
    final start = (page.page - 1) * page.pageSize;
    final end = (start + page.pageSize).clamp(0, allItems.length);
    final List<T> items =
        start < allItems.length ? allItems.sublist(start, end) : <T>[];
    return PaginatedResult<T>(
      items: items,
      total: allItems.length,
      page: page.page,
      pageSize: page.pageSize,
      hasMore: end < allItems.length,
    );
  }
}
