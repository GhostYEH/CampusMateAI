import 'package:equatable/equatable.dart';

/// 通用分页结果 — 对齐后端分页模型(items/total/page/page_size/has_more)。
///
/// 后端使用 snake_case,Dart 模型通过工厂构造适配。
class PaginatedResult<T> extends Equatable {
  const PaginatedResult({
    required this.items,
    required this.total,
    required this.page,
    required this.pageSize,
    required this.hasMore,
  });

  final List<T> items;
  final int total;
  final int page;
  final int pageSize;
  final bool hasMore;

  /// 是否还有下一页(基于 hasMore,与后端语义对齐)。
  bool get canLoadMore => hasMore && items.length < total;

  /// 当前页起始索引(用于 ListView offset)。
  int get offset => (page - 1) * pageSize;

  /// 重新映射 items 类型(用于将原始 Map 转 Model)。
  PaginatedResult<R> map<R>(List<R> items) {
    return PaginatedResult<R>(
      items: items,
      total: total,
      page: page,
      pageSize: pageSize,
      hasMore: hasMore,
    );
  }

  /// 从后端返回的 JSON 构造分页结果。
  ///
  /// [itemMapper] 用于将 items 中的每个 Map 转为 T。
  /// 兼容 snake_case 字段(page_size / has_more)。
  static PaginatedResult<T> fromJson<T>(
    Map<String, dynamic> json,
    T Function(Map<String, dynamic>) itemMapper,
  ) {
    final rawItems = json['items'] as List? ?? const [];
    return PaginatedResult<T>(
      items: rawItems
          .whereType<Map<String, dynamic>>()
          .map(itemMapper)
          .toList(growable: false),
      total: (json['total'] as num?)?.toInt() ?? 0,
      page: (json['page'] as num?)?.toInt() ?? 1,
      pageSize: (json['page_size'] as num?)?.toInt() ??
          (json['pageSize'] as num?)?.toInt() ??
          20,
      hasMore: json['has_more'] as bool? ?? json['hasMore'] as bool? ?? false,
    );
  }

  /// 空结果。
  static PaginatedResult<T> empty<T>({int pageSize = 20}) {
    return PaginatedResult<T>(
      items: const [],
      total: 0,
      page: 1,
      pageSize: pageSize,
      hasMore: false,
    );
  }

  @override
  List<Object?> get props => [items, total, page, pageSize, hasMore];
}

/// 分页请求参数。
class PageRequest extends Equatable {
  const PageRequest({
    this.page = 1,
    this.pageSize = 20,
    this.search,
    this.filters = const {},
    this.sortBy,
    this.sortDesc = false,
  });

  final int page;
  final int pageSize;
  final String? search;
  final Map<String, dynamic> filters;
  final String? sortBy;
  final bool sortDesc;

  /// 计算偏移量。
  int get offset => (page - 1) * pageSize;

  /// 下一页请求(若 hasMore)。
  PageRequest next() => copyWith(page: page + 1);

  /// 重置到第一页(用于刷新 / 切换筛选)。
  PageRequest reset() => copyWith(page: 1);

  PageRequest copyWith({
    int? page,
    int? pageSize,
    String? search,
    Map<String, dynamic>? filters,
    String? sortBy,
    bool? sortDesc,
  }) {
    return PageRequest(
      page: page ?? this.page,
      pageSize: pageSize ?? this.pageSize,
      search: search ?? this.search,
      filters: filters ?? this.filters,
      sortBy: sortBy ?? this.sortBy,
      sortDesc: sortDesc ?? this.sortDesc,
    );
  }

  @override
  List<Object?> get props =>
      [page, pageSize, search, filters, sortBy, sortDesc];
}
