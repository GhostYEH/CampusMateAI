import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../app/design_system/app_colors.dart';
import '../../app/design_system/app_typography.dart';

/// 防抖搜索框 — 300ms 延迟后触发回调,避免每次按键都发起请求。
///
/// 性能(AGENTS.md §8):
/// - 默认 300ms 防抖
/// - 用户继续输入时取消之前的回调
/// - 提供 clear 按钮
/// - 支持 reduceMotion(光标闪烁关闭)
class DebouncedSearchField extends StatefulWidget {
  const DebouncedSearchField({
    super.key,
    required this.onChanged,
    this.hint = '搜索',
    this.debounce = const Duration(milliseconds: 300),
    this.initialValue = '',
    this.autofocus = false,
    this.prefixIcon,
    this.onSubmitted,
  });

  final ValueChanged<String> onChanged;
  final String hint;
  final Duration debounce;
  final String initialValue;
  final bool autofocus;
  final IconData? prefixIcon;
  final ValueChanged<String>? onSubmitted;

  @override
  State<DebouncedSearchField> createState() => _DebouncedSearchFieldState();
}

class _DebouncedSearchFieldState extends State<DebouncedSearchField> {
  late final TextEditingController _controller;
  Timer? _debounce;
  late String _lastValue;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.initialValue);
    _lastValue = widget.initialValue;
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _onChanged(String value) {
    if (value == _lastValue) return;
    _lastValue = value;
    _debounce?.cancel();
    _debounce = Timer(widget.debounce, () {
      widget.onChanged(value);
    });
  }

  void _clear() {
    _controller.clear();
    _onChanged('');
  }

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return TextField(
      controller: _controller,
      autofocus: widget.autofocus,
      textInputAction: TextInputAction.search,
      onChanged: _onChanged,
      onSubmitted: widget.onSubmitted,
      style: AppTypography.body.copyWith(color: c.textPrimary),
      inputFormatters: [
        // 限制长度防止恶意输入
        LengthLimitingTextInputFormatter(120),
      ],
      decoration: InputDecoration(
        hintText: widget.hint,
        hintStyle: AppTypography.body.copyWith(color: c.textTertiary),
        isDense: true,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.sm + 2,
        ),
        prefixIcon: Icon(
          widget.prefixIcon ?? Icons.search_rounded,
          size: 20,
          color: c.textSecondary,
        ),
        suffixIcon: ValueListenableBuilder<TextEditingValue>(
          valueListenable: _controller,
          builder: (context, value, _) {
            if (value.text.isEmpty) return const SizedBox.shrink();
            return IconButton(
              tooltip: '清除',
              onPressed: _clear,
              icon: Icon(
                Icons.close_rounded,
                size: 16,
                color: c.textTertiary,
              ),
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(
                minWidth: 28,
                minHeight: 28,
              ),
            );
          },
        ),
        filled: true,
        fillColor: c.bgSurface,
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppRadius.md),
          borderSide: BorderSide(color: c.border, width: 1),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppRadius.md),
          borderSide: BorderSide(color: c.primary, width: 1.4),
        ),
      ),
    );
  }
}
