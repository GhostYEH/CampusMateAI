import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/auth_providers.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../data/models/auth.dart';

/// 登录页 — 真实认证入口。
///
/// 设计原则(遵循 frontend-design skill 与 AGENTS.md §2):
/// - 低饱和青蓝主色,暖色用于错误与提示点缀
/// - 必须调用真实认证接口,不提供任何绕过认证的快捷登录
/// - 用户名可预填,但密码必须由用户输入并经后端校验
/// - 错误以可读文案展示,不暴露技术细节
/// - 加载状态防重复点击
/// - 不在日志打印 token,不持久化密码
/// - 后端不可用时显示"服务暂时不可用 / 重试",保留用户输入
class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({super.key, this.initialError});

  /// 由路由重定向注入的初始错误信息(如 session 过期)。
  final String? initialError;

  @override
  ConsumerState<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage> {
  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  final FocusNode _usernameFocus = FocusNode();
  final FocusNode _passwordFocus = FocusNode();
  bool _obscurePassword = true;

  @override
  void initState() {
    super.initState();
    if (widget.initialError != null) {
      // 下一帧注入错误信息,避免在 build 中修改状态
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        ref.read(authNotifierProvider.notifier).clearError();
        setState(() {});
      });
    }
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    _usernameFocus.dispose();
    _passwordFocus.dispose();
    super.dispose();
  }

  Future<void> _login(LoginCredentials credentials) async {
    // 防重复点击
    final status = ref.read(authNotifierProvider).status;
    if (status == AuthStatus.loading) return;

    FocusScope.of(context).unfocus();
    await ref.read(authNotifierProvider.notifier).login(credentials);
    // 路由监听器会自动处理跳转
  }

  Future<void> _submit() async {
    final username = _usernameController.text.trim();
    final password = _passwordController.text;
    if (username.isEmpty || password.isEmpty) return;
    await _login(LoginCredentials(username: username, password: password));
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authNotifierProvider);
    final c = context.appColors;

    final errorMessage = auth.errorMessage ?? widget.initialError;
    final isLoading = auth.status == AuthStatus.loading;

    return Scaffold(
      backgroundColor: c.bgBase,
      body: SafeArea(
        child: MediaQuery.of(context).size.height < 600
            ? _buildCompact(context, c, errorMessage, isLoading)
            : _buildStandard(context, c, errorMessage, isLoading),
      ),
    );
  }

  Widget _buildStandard(
    BuildContext context,
    AppColorScheme c,
    String? errorMessage,
    bool isLoading,
  ) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.edge,
          vertical: AppSpacing.xl,
        ),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            mainAxisSize: MainAxisSize.min,
            children: [
              const _BrandHeader(key: ValueKey('brand_header')),
              const SizedBox(height: AppSpacing.xl),
              StaggeredEnter(
                delay: const Duration(milliseconds: 120),
                child: Text(
                  '账号登录',
                  style: AppTypography.subtitle.copyWith(color: c.textPrimary),
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              if (errorMessage != null) ...[
                StaggeredEnter(
                  child: _ErrorBanner(message: errorMessage),
                ),
                const SizedBox(height: AppSpacing.md),
              ],
              StaggeredEnter(
                delay: const Duration(milliseconds: 180),
                child: _LoginForm(
                  usernameController: _usernameController,
                  passwordController: _passwordController,
                  usernameFocus: _usernameFocus,
                  passwordFocus: _passwordFocus,
                  obscurePassword: _obscurePassword,
                  isLoading: isLoading,
                  onToggleObscure: () => setState(
                    () => _obscurePassword = !_obscurePassword,
                  ),
                  onSubmit: _submit,
                ),
              ),
              const SizedBox(height: AppSpacing.xxl),
              const StaggeredEnter(
                delay: Duration(milliseconds: 360),
                child: _FooterNote(),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildCompact(
    BuildContext context,
    AppColorScheme c,
    String? errorMessage,
    bool isLoading,
  ) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSpacing.edge),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const _BrandHeader(key: ValueKey('brand_header_compact')),
          const SizedBox(height: AppSpacing.md),
          if (errorMessage != null) ...[
            _ErrorBanner(message: errorMessage),
            const SizedBox(height: AppSpacing.md),
          ],
          _LoginForm(
            usernameController: _usernameController,
            passwordController: _passwordController,
            usernameFocus: _usernameFocus,
            passwordFocus: _passwordFocus,
            obscurePassword: _obscurePassword,
            isLoading: isLoading,
            onToggleObscure: () => setState(
              () => _obscurePassword = !_obscurePassword,
            ),
            onSubmit: _submit,
          ),
        ],
      ),
    );
  }
}

/// 品牌头部 — 校园 AI 陪伴助手 Logo + 标语。
class _BrandHeader extends StatelessWidget {
  const _BrandHeader({super.key});

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: c.primary,
                borderRadius: BorderRadius.circular(AppRadius.md),
              ),
              child: const Icon(
                Icons.school_rounded,
                color: AppColors.onPrimary,
                size: 26,
              ),
            ),
            const SizedBox(width: AppSpacing.md),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'CampusMate AI',
                  style: AppTypography.headline.copyWith(color: c.textPrimary),
                ),
                const SizedBox(height: 2),
                Text(
                  '校园事务智能陪伴助手',
                  style: AppTypography.caption.copyWith(color: c.textSecondary),
                ),
              ],
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.md),
        Text(
          '欢迎回来',
          style: AppTypography.title.copyWith(color: c.textPrimary),
        ),
        const SizedBox(height: 4),
        Text(
          '登录后即可使用通知整理、任务提醒、AI 导员与学习陪伴。',
          style: AppTypography.body.copyWith(color: c.textSecondary),
        ),
      ],
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm + 2,
      ),
      decoration: BoxDecoration(
        color: c.danger.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(AppRadius.sm),
        border: Border.all(color: c.danger.withValues(alpha: 0.3), width: 1),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.error_outline_rounded, size: 18, color: c.danger),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              message,
              style: AppTypography.caption.copyWith(color: c.danger),
            ),
          ),
        ],
      ),
    );
  }
}

class _LoginForm extends StatelessWidget {
  const _LoginForm({
    required this.usernameController,
    required this.passwordController,
    required this.usernameFocus,
    required this.passwordFocus,
    required this.obscurePassword,
    required this.isLoading,
    required this.onToggleObscure,
    required this.onSubmit,
  });

  final TextEditingController usernameController;
  final TextEditingController passwordController;
  final FocusNode usernameFocus;
  final FocusNode passwordFocus;
  final bool obscurePassword;
  final bool isLoading;
  final VoidCallback onToggleObscure;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _TextField(
          controller: usernameController,
          focusNode: usernameFocus,
          label: '账号',
          hint: '请输入用户名或学号 / 工号',
          prefixIcon: Icons.person_outline_rounded,
          textInputAction: TextInputAction.next,
          onSubmitted: (_) => passwordFocus.requestFocus(),
        ),
        const SizedBox(height: AppSpacing.md),
        _TextField(
          controller: passwordController,
          focusNode: passwordFocus,
          label: '密码',
          hint: '请输入密码',
          prefixIcon: Icons.lock_outline_rounded,
          obscure: obscurePassword,
          suffix: IconButton(
            tooltip: obscurePassword ? '显示密码' : '隐藏密码',
            icon: Icon(
              obscurePassword
                  ? Icons.visibility_off_outlined
                  : Icons.visibility_outlined,
              size: 20,
              color: c.textSecondary,
            ),
            onPressed: onToggleObscure,
          ),
          textInputAction: TextInputAction.done,
          onSubmitted: (_) => onSubmit(),
        ),
        const SizedBox(height: AppSpacing.md),
        FilledButton.icon(
          onPressed: isLoading ? null : onSubmit,
          style: FilledButton.styleFrom(
            backgroundColor: c.primary,
            foregroundColor: c.onPrimary,
            padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(AppRadius.md),
            ),
          ),
          icon: isLoading
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    valueColor: AlwaysStoppedAnimation(Colors.white),
                  ),
                )
              : const Icon(Icons.login_rounded, size: 20),
          label: Text(
            isLoading ? '登录中...' : '登录',
            style: AppTypography.bodyStrong.copyWith(color: c.onPrimary),
          ),
        ),
      ],
    );
  }
}

class _TextField extends StatelessWidget {
  const _TextField({
    required this.controller,
    required this.focusNode,
    required this.label,
    required this.hint,
    required this.prefixIcon,
    this.obscure = false,
    this.suffix,
    this.textInputAction,
    this.onSubmitted,
  });

  final TextEditingController controller;
  final FocusNode focusNode;
  final String label;
  final String hint;
  final IconData prefixIcon;
  final bool obscure;
  final Widget? suffix;
  final TextInputAction? textInputAction;
  final ValueChanged<String>? onSubmitted;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: AppTypography.label.copyWith(color: c.textSecondary),
        ),
        const SizedBox(height: 4),
        TextField(
          controller: controller,
          focusNode: focusNode,
          obscureText: obscure,
          textInputAction: textInputAction,
          onSubmitted: onSubmitted,
          style: AppTypography.body.copyWith(color: c.textPrimary),
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: AppTypography.body.copyWith(color: c.textTertiary),
            prefixIcon: Icon(prefixIcon, size: 20, color: c.textSecondary),
            suffixIcon: suffix,
            filled: true,
            fillColor: c.bgSurface,
            contentPadding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.md,
              vertical: AppSpacing.md,
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(AppRadius.md),
              borderSide: BorderSide(color: c.border, width: 1),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(AppRadius.md),
              borderSide: BorderSide(color: c.primary, width: 1.4),
            ),
          ),
        ),
      ],
    );
  }
}

class _FooterNote extends StatelessWidget {
  const _FooterNote();

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Column(
      children: [
        Text(
          '登录即表示同意遵守校园网络安全规范',
          style: AppTypography.overline.copyWith(color: c.textTertiary),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 4),
        Text(
          '密码不存储在本地,token 经过混淆保存',
          style: AppTypography.overline.copyWith(
            color: c.textTertiary,
            fontSize: 10,
          ),
          textAlign: TextAlign.center,
        ),
      ],
    );
  }
}
