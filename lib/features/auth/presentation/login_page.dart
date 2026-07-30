import 'dart:async';
import 'dart:math' as math;
import 'dart:ui';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:video_player/video_player.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/auth_providers.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../core/widgets/state_views.dart';
import '../../../data/models/auth.dart';
import '../data/login_preference_service.dart';

const _night = Color(0xFF020A1D);
const _panel = Color(0x780A1931);
const _line = Color(0x52D6ECFF);
const _textPrimary = Color(0xFFF5F8FF);
const _textSecondary = Color(0xFF9BADCA);
const _cyan = Color(0xFF63D9EA);
const _blue = Color(0xFF5B83FF);

/// 真实认证入口。背景与按钮动效均支持“减少动态效果”设置。
class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({super.key, this.initialError});

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
  bool _rememberUsername = false;
  String? _validationMessage;

  @override
  void initState() {
    super.initState();
    _restoreRememberedUsername();
  }

  Future<void> _restoreRememberedUsername() async {
    final username =
        await ref.read(loginPreferenceServiceProvider).loadRememberedUsername();
    if (!mounted || username == null || username.isEmpty) return;
    setState(() {
      _usernameController.text = username;
      _rememberUsername = true;
    });
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    _usernameFocus.dispose();
    _passwordFocus.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (ref.read(authNotifierProvider).status == AuthStatus.loading) return;

    final username = _usernameController.text.trim();
    final password = _passwordController.text;
    if (username.isEmpty || password.isEmpty) {
      setState(() {
        _validationMessage = username.isEmpty ? '请输入账号后继续。' : '请输入密码后继续。';
      });
      (username.isEmpty ? _usernameFocus : _passwordFocus).requestFocus();
      return;
    }

    setState(() => _validationMessage = null);
    FocusScope.of(context).unfocus();
    unawaited(
      ref
          .read(loginPreferenceServiceProvider)
          .rememberUsername(_rememberUsername ? username : null),
    );
    await ref
        .read(authNotifierProvider.notifier)
        .login(LoginCredentials(username: username, password: password));
  }

  void _showPasswordHelp() {
    FocusScope.of(context).unfocus();
    showDialog<void>(
      context: context,
      builder: (context) => const _PasswordHelpDialog(),
    );
  }

  void _goRegister() {
    // 登录进行中禁止跳转,避免状态错乱
    if (ref.read(authNotifierProvider).status == AuthStatus.loading) return;
    FocusScope.of(context).unfocus();
    // 把当前输入的用户名带过去,方便注册时预填
    final username = _usernameController.text.trim();
    context.go(
      '/register',
      extra: username.isEmpty ? null : username,
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authNotifierProvider);
    final errorMessage =
        _validationMessage ?? auth.errorMessage ?? widget.initialError;
    final isLoading = auth.status == AuthStatus.loading;

    return Scaffold(
      backgroundColor: _night,
      body: Stack(
        fit: StackFit.expand,
        children: [
          const _AnimatedCampusBackground(),
          SafeArea(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final useWebLayout = kIsWeb && constraints.maxWidth >= 900;
                if (useWebLayout) {
                  return _WebLoginLayout(
                    form: _buildForm(errorMessage, isLoading),
                  );
                }
                return _MobileLoginLayout(
                  compact: constraints.maxHeight < 700,
                  form: _buildForm(errorMessage, isLoading),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildForm(String? errorMessage, bool isLoading) {
    return _LoginPanel(
      usernameController: _usernameController,
      passwordController: _passwordController,
      usernameFocus: _usernameFocus,
      passwordFocus: _passwordFocus,
      obscurePassword: _obscurePassword,
      rememberUsername: _rememberUsername,
      isLoading: isLoading,
      errorMessage: errorMessage,
      onToggleObscure: () {
        setState(() => _obscurePassword = !_obscurePassword);
      },
      onRememberChanged: (value) {
        setState(() => _rememberUsername = value);
      },
      onForgotPassword: _showPasswordHelp,
      onRegister: _goRegister,
      onSubmit: _submit,
    );
  }
}

class _MobileLoginLayout extends StatelessWidget {
  const _MobileLoginLayout({
    required this.compact,
    required this.form,
  });

  final bool compact;
  final Widget form;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(20, compact ? 12 : 28, 20, 24),
      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 430),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              StaggeredEnter(
                child: compact
                    ? const _CompactBrandLockup()
                    : const _BrandLockup(centered: true),
              ),
              SizedBox(height: compact ? 12 : 26),
              StaggeredEnter(
                delay: const Duration(milliseconds: 100),
                child: form,
              ),
              SizedBox(height: compact ? 14 : 22),
              if (!compact)
                const StaggeredEnter(
                  delay: Duration(milliseconds: 220),
                  child: _FeatureRail(compact: true),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CompactBrandLockup extends StatelessWidget {
  const _CompactBrandLockup();

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(13),
            gradient: const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFF5B8DFF), Color(0xFF2555C7)],
            ),
          ),
          child: const Icon(
            Icons.school_rounded,
            color: Colors.white,
            size: 24,
          ),
        ),
        const SizedBox(width: 11),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'CampusMate AI',
              style: AppTypography.title.copyWith(color: _textPrimary),
            ),
            Text(
              '校园事务智能陪伴助手',
              style: AppTypography.overline.copyWith(
                color: _textSecondary,
                letterSpacing: 0.5,
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _WebLoginLayout extends StatelessWidget {
  const _WebLoginLayout({required this.form});

  final Widget form;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 56, vertical: 36),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1280),
          child: Row(
            children: [
              const Expanded(
                flex: 6,
                child: Padding(
                  padding: EdgeInsets.only(right: 52),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      StaggeredEnter(child: _BrandLockup()),
                      SizedBox(height: 34),
                      StaggeredEnter(
                        delay: Duration(milliseconds: 120),
                        child: _WebWelcome(),
                      ),
                      SizedBox(height: 34),
                      StaggeredEnter(
                        delay: Duration(milliseconds: 220),
                        child: _FeatureRail(),
                      ),
                    ],
                  ),
                ),
              ),
              Flexible(
                flex: 4,
                child: Align(
                  alignment: Alignment.centerRight,
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 460),
                    child: StaggeredEnter(
                      delay: const Duration(milliseconds: 160),
                      child: form,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _BrandLockup extends StatelessWidget {
  const _BrandLockup({this.centered = false});

  final bool centered;

  @override
  Widget build(BuildContext context) {
    final content = Column(
      crossAxisAlignment:
          centered ? CrossAxisAlignment.center : CrossAxisAlignment.start,
      children: [
        Container(
          width: 58,
          height: 58,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(17),
            gradient: const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFF5B8DFF), Color(0xFF2555C7)],
            ),
            border: Border.all(color: Colors.white.withValues(alpha: 0.18)),
            boxShadow: const [
              BoxShadow(
                color: Color(0x553875F4),
                blurRadius: 28,
                offset: Offset(0, 10),
              ),
            ],
          ),
          child: const Icon(
            Icons.school_rounded,
            color: Colors.white,
            size: 31,
          ),
        ),
        const SizedBox(height: 13),
        Text(
          'CampusMate AI',
          style: AppTypography.headline.copyWith(
            color: _textPrimary,
            fontSize: 24,
            letterSpacing: -0.5,
          ),
        ),
        const SizedBox(height: 3),
        Text(
          '校园事务智能陪伴助手',
          style: AppTypography.caption.copyWith(
            color: _textSecondary,
            letterSpacing: 1.2,
          ),
        ),
        const SizedBox(height: 15),
        Text(
          '智能协同  ·  高效学习  ·  连接校园',
          textAlign: centered ? TextAlign.center : TextAlign.left,
          style: AppTypography.caption.copyWith(
            color: _textSecondary.withValues(alpha: 0.86),
            letterSpacing: 1.1,
          ),
        ),
      ],
    );

    if (!centered) return content;
    return Center(child: content);
  }
}

class _WebWelcome extends StatelessWidget {
  const _WebWelcome();

  @override
  Widget build(BuildContext context) {
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 560),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '欢迎回来，\n把今天的校园生活理清楚。',
            style: AppTypography.display.copyWith(
              color: _textPrimary,
              fontSize: 42,
              height: 1.22,
              letterSpacing: -1.1,
            ),
          ),
          const SizedBox(height: 16),
          Text(
            '通知、任务、学习陪伴和 AI 导员，都在同一个清晰的入口。',
            style: AppTypography.body.copyWith(
              color: _textSecondary,
              fontSize: 16,
              height: 1.65,
            ),
          ),
        ],
      ),
    );
  }
}

class _LoginPanel extends StatelessWidget {
  const _LoginPanel({
    required this.usernameController,
    required this.passwordController,
    required this.usernameFocus,
    required this.passwordFocus,
    required this.obscurePassword,
    required this.rememberUsername,
    required this.isLoading,
    required this.errorMessage,
    required this.onToggleObscure,
    required this.onRememberChanged,
    required this.onForgotPassword,
    required this.onRegister,
    required this.onSubmit,
  });

  final TextEditingController usernameController;
  final TextEditingController passwordController;
  final FocusNode usernameFocus;
  final FocusNode passwordFocus;
  final bool obscurePassword;
  final bool rememberUsername;
  final bool isLoading;
  final String? errorMessage;
  final VoidCallback onToggleObscure;
  final ValueChanged<bool> onRememberChanged;
  final VoidCallback onForgotPassword;
  final VoidCallback onRegister;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(26),
      child: BackdropFilter(
        // 保留视频纹理，只做轻量柔化；这是 Flutter 中的液态玻璃近似。
        filter: ImageFilter.blur(sigmaX: 8, sigmaY: 8),
        child: Container(
          padding: const EdgeInsets.fromLTRB(22, 22, 22, 18),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                Color(0x9A18324A),
                _panel,
                Color(0x66102035),
              ],
              stops: [0, 0.48, 1],
            ),
            borderRadius: BorderRadius.circular(26),
            border: Border.all(color: _line),
            boxShadow: const [
              BoxShadow(
                color: Color(0x5200091C),
                blurRadius: 32,
                offset: Offset(0, 14),
              ),
              BoxShadow(
                color: Color(0x26DDF6FF),
                blurRadius: 1,
                offset: Offset(0, -1),
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                '欢迎回来',
                style: AppTypography.title.copyWith(
                  color: _textPrimary,
                  fontSize: 18,
                ),
              ),
              const SizedBox(height: 3),
              Text(
                '账号登录',
                style: AppTypography.caption.copyWith(color: _textSecondary),
              ),
              if (errorMessage != null) ...[
                const SizedBox(height: 14),
                _ErrorBanner(message: errorMessage!),
              ],
              const SizedBox(height: 18),
              _NightTextField(
                controller: usernameController,
                focusNode: usernameFocus,
                label: '账号',
                hint: '请输入学号 / 工号 / 用户名',
                prefixIcon: Icons.person_outline_rounded,
                textInputAction: TextInputAction.next,
                onChanged: (_) {},
                onSubmitted: (_) => passwordFocus.requestFocus(),
              ),
              const SizedBox(height: 15),
              _NightTextField(
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
                    color: _textSecondary,
                  ),
                  onPressed: onToggleObscure,
                ),
                textInputAction: TextInputAction.done,
                onChanged: (_) {},
                onSubmitted: (_) => onSubmit(),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  SizedBox(
                    width: 28,
                    height: 32,
                    child: Checkbox(
                      value: rememberUsername,
                      onChanged: isLoading
                          ? null
                          : (value) => onRememberChanged(value ?? false),
                      activeColor: _blue,
                      checkColor: Colors.white,
                      side: const BorderSide(color: _textSecondary),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                  ),
                  const SizedBox(width: 5),
                  Expanded(
                    child: GestureDetector(
                      onTap: isLoading
                          ? null
                          : () => onRememberChanged(!rememberUsername),
                      child: Text(
                        '记住账号',
                        style: AppTypography.caption.copyWith(
                          color: _textSecondary,
                        ),
                      ),
                    ),
                  ),
                  TextButton(
                    onPressed: isLoading ? null : onForgotPassword,
                    style: TextButton.styleFrom(
                      foregroundColor: _cyan,
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      minimumSize: const Size(0, 40),
                    ),
                    child: const Text('忘记密码？'),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              _PrismaticLoginButton(
                isLoading: isLoading,
                onPressed: onSubmit,
              ),
              const SizedBox(height: 17),
              Text(
                '登录即表示同意遵守《校园网络安全规范》',
                textAlign: TextAlign.center,
                style: AppTypography.overline.copyWith(
                  color: _textSecondary.withValues(alpha: 0.78),
                  fontWeight: FontWeight.w400,
                  letterSpacing: 0,
                ),
              ),
              const SizedBox(height: 14),
              // 注册入口 — 与登录按钮形成对称动作,
              // 用 OutlinedBorder 保持视觉层级低于主登录按钮
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    '还没有账号?',
                    style: AppTypography.caption.copyWith(
                      color: _textSecondary,
                    ),
                  ),
                  TextButton(
                    onPressed: isLoading ? null : onRegister,
                    style: TextButton.styleFrom(
                      foregroundColor: _cyan,
                      padding: const EdgeInsets.symmetric(horizontal: 6),
                      minimumSize: const Size(0, 36),
                    ),
                    child: const Text('注册账号'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NightTextField extends StatelessWidget {
  const _NightTextField({
    required this.controller,
    required this.focusNode,
    required this.label,
    required this.hint,
    required this.prefixIcon,
    required this.onChanged,
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
  final ValueChanged<String> onChanged;
  final bool obscure;
  final Widget? suffix;
  final TextInputAction? textInputAction;
  final ValueChanged<String>? onSubmitted;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: AppTypography.label.copyWith(color: _textPrimary),
        ),
        const SizedBox(height: 7),
        TextField(
          controller: controller,
          focusNode: focusNode,
          obscureText: obscure,
          textInputAction: textInputAction,
          onChanged: onChanged,
          onSubmitted: onSubmitted,
          autofillHints: obscure
              ? const [AutofillHints.password]
              : const [AutofillHints.username],
          cursorColor: _cyan,
          style: AppTypography.body.copyWith(color: _textPrimary),
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: AppTypography.body.copyWith(
              color: _textSecondary.withValues(alpha: 0.64),
            ),
            prefixIcon: Icon(prefixIcon, size: 20, color: _textSecondary),
            suffixIcon: suffix,
            filled: true,
            fillColor: const Color(0x52101E37),
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 14,
              vertical: 15,
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: _line),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: _cyan, width: 1.4),
            ),
          ),
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
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.danger.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: AppColors.danger.withValues(alpha: 0.42),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.error_outline_rounded,
            size: 18,
            color: Color(0xFFFF9B98),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: AppTypography.caption.copyWith(
                color: const Color(0xFFFFC6C4),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _PrismaticLoginButton extends ConsumerStatefulWidget {
  const _PrismaticLoginButton({
    required this.isLoading,
    required this.onPressed,
  });

  final bool isLoading;
  final VoidCallback onPressed;

  @override
  ConsumerState<_PrismaticLoginButton> createState() =>
      _PrismaticLoginButtonState();
}

class _PrismaticLoginButtonState extends ConsumerState<_PrismaticLoginButton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 7600),
    );
    if (!ref.read(reduceMotionProvider)) {
      _controller.repeat();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _syncMotion(bool reduceMotion) {
    if (reduceMotion) {
      _controller.stop();
    } else if (!_controller.isAnimating) {
      _controller.repeat();
    }
  }

  @override
  Widget build(BuildContext context) {
    final reduceMotion = ref.watch(reduceMotionProvider) ||
        (MediaQuery.maybeOf(context)?.accessibleNavigation ?? false);
    ref.listen<bool>(reduceMotionProvider, (_, next) => _syncMotion(next));

    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        final t = reduceMotion ? 0.12 : _controller.value;
        // 两组谐波改变相位推进速度，始终向前但不会机械匀速循环。
        final phase = (t +
                math.sin(t * math.pi * 2) * 0.06 +
                math.sin(t * math.pi * 6) * 0.018) %
            1.0;
        final hue = phase * 360;
        final colors = List<Color>.generate(5, (index) {
          return HSVColor.fromAHSV(
            1,
            (hue + index * 58) % 360,
            index == 3 ? 0.54 : 0.72,
            0.98,
          ).toColor();
        });

        return DecoratedBox(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            gradient: LinearGradient(
              begin: Alignment(
                math.cos(phase * math.pi * 2),
                math.sin(phase * math.pi * 2),
              ),
              end: Alignment(
                -math.cos(phase * math.pi * 2),
                -math.sin(phase * math.pi * 2),
              ),
              colors: colors,
            ),
            boxShadow: [
              BoxShadow(
                color: colors[2].withValues(alpha: 0.22),
                blurRadius: 22,
                offset: const Offset(0, 9),
              ),
            ],
          ),
          child: child,
        );
      },
      child: FilledButton.icon(
        onPressed: widget.isLoading ? null : widget.onPressed,
        style: FilledButton.styleFrom(
          backgroundColor: Colors.transparent,
          disabledBackgroundColor: Colors.transparent,
          foregroundColor: Colors.white,
          disabledForegroundColor: Colors.white.withValues(alpha: 0.82),
          shadowColor: Colors.transparent,
          padding: const EdgeInsets.symmetric(vertical: 15),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
        icon: widget.isLoading
            ? const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  valueColor: AlwaysStoppedAnimation(Colors.white),
                ),
              )
            : const Icon(Icons.login_rounded, size: 20),
        label: Text(
          widget.isLoading ? '登录中...' : '登录',
          style: AppTypography.bodyStrong.copyWith(color: Colors.white),
        ),
      ),
    );
  }
}

class _FeatureRail extends StatelessWidget {
  const _FeatureRail({this.compact = false});

  final bool compact;

  @override
  Widget build(BuildContext context) {
    const items = [
      (Icons.notifications_active_outlined, '通知智能整理', '重要信息不遗漏'),
      (Icons.event_note_outlined, '任务协同管理', '学习事务更清楚'),
      (Icons.psychology_alt_outlined, 'AI 导员陪伴', '答疑提醒更专业'),
    ];

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var index = 0; index < items.length; index++) ...[
          if (index > 0)
            Container(
              width: 1,
              height: compact ? 58 : 66,
              margin: EdgeInsets.symmetric(horizontal: compact ? 8 : 18),
              color: _line,
            ),
          Expanded(
            child: _FeatureItem(
              icon: items[index].$1,
              title: items[index].$2,
              caption: items[index].$3,
              compact: compact,
            ),
          ),
        ],
      ],
    );
  }
}

class _FeatureItem extends StatelessWidget {
  const _FeatureItem({
    required this.icon,
    required this.title,
    required this.caption,
    required this.compact,
  });

  final IconData icon;
  final String title;
  final String caption;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment:
          compact ? CrossAxisAlignment.center : CrossAxisAlignment.start,
      children: [
        Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            color: _blue.withValues(alpha: 0.17),
            borderRadius: BorderRadius.circular(11),
            border: Border.all(color: _blue.withValues(alpha: 0.26)),
          ),
          child: Icon(icon, size: 19, color: _cyan),
        ),
        const SizedBox(height: 8),
        Text(
          title,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          textAlign: compact ? TextAlign.center : TextAlign.left,
          style: AppTypography.label.copyWith(
            color: _textPrimary,
            fontSize: compact ? 10.5 : 12,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          caption,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          textAlign: compact ? TextAlign.center : TextAlign.left,
          style: AppTypography.overline.copyWith(
            color: _textSecondary,
            fontSize: compact ? 9 : 10.5,
            letterSpacing: 0,
          ),
        ),
      ],
    );
  }
}

class _PasswordHelpDialog extends StatefulWidget {
  const _PasswordHelpDialog();

  @override
  State<_PasswordHelpDialog> createState() => _PasswordHelpDialogState();
}

class _PasswordHelpDialogState extends State<_PasswordHelpDialog> {
  final _controller = TextEditingController();
  bool _submitted = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      backgroundColor: const Color(0xFF0C1B33),
      surfaceTintColor: Colors.transparent,
      title: Text(
        _submitted ? '已记录申请' : '找回密码',
        style: const TextStyle(color: _textPrimary),
      ),
      content: SizedBox(
        width: 380,
        child: _submitted
            ? Text(
                '请携带校园卡联系学校信息中心核验身份。当前版本不会发送短信或邮件。',
                style: AppTypography.body.copyWith(color: _textSecondary),
              )
            : TextField(
                controller: _controller,
                autofocus: true,
                style: const TextStyle(color: _textPrimary),
                decoration: const InputDecoration(
                  labelText: '学号或工号',
                  labelStyle: TextStyle(color: _textSecondary),
                  enabledBorder: OutlineInputBorder(
                    borderSide: BorderSide(color: _line),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderSide: BorderSide(color: _cyan),
                  ),
                ),
              ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(_submitted ? '知道了' : '取消'),
        ),
        if (!_submitted)
          FilledButton(
            onPressed: () {
              if (_controller.text.trim().isEmpty) return;
              setState(() => _submitted = true);
            },
            child: const Text('提交申请'),
          ),
      ],
    );
  }
}

class _AnimatedCampusBackground extends ConsumerStatefulWidget {
  const _AnimatedCampusBackground();

  @override
  ConsumerState<_AnimatedCampusBackground> createState() =>
      _AnimatedCampusBackgroundState();
}

class _AnimatedCampusBackgroundState
    extends ConsumerState<_AnimatedCampusBackground>
    with SingleTickerProviderStateMixin, WidgetsBindingObserver {
  late final AnimationController _controller;
  late final VideoPlayerController _videoController;
  bool _videoReady = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 18),
    );
    if (!ref.read(reduceMotionProvider)) {
      _controller.repeat();
    }
    _videoController = VideoPlayerController.asset('assets/videos/kp.mp4');
    unawaited(_initializeVideo());
  }

  Future<void> _initializeVideo() async {
    try {
      await _videoController.initialize();
      await _videoController.setLooping(true);
      await _videoController.setVolume(0);
      if (!ref.read(reduceMotionProvider)) {
        await _videoController.play();
      }
      if (mounted) setState(() => _videoReady = true);
    } catch (_) {
      // 测试环境或不支持视频的平台使用静态校园图作为可靠降级。
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _videoController.dispose();
    _controller.dispose();
    super.dispose();
  }

  void _syncMotion(bool reduceMotion) {
    if (reduceMotion) {
      _controller.stop();
      if (_videoReady) unawaited(_videoController.pause());
    } else if (!_controller.isAnimating) {
      _controller.repeat();
      if (_videoReady) unawaited(_videoController.play());
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (!_videoReady) return;
    if (state == AppLifecycleState.resumed && !ref.read(reduceMotionProvider)) {
      unawaited(_videoController.play());
    } else if (state != AppLifecycleState.resumed) {
      unawaited(_videoController.pause());
    }
  }

  @override
  Widget build(BuildContext context) {
    final reduceMotion = ref.watch(reduceMotionProvider) ||
        (MediaQuery.maybeOf(context)?.accessibleNavigation ?? false);
    ref.listen<bool>(reduceMotionProvider, (_, next) => _syncMotion(next));

    return LayoutBuilder(
      builder: (context, constraints) {
        final isWideWeb = kIsWeb && constraints.maxWidth >= 900;
        return AnimatedBuilder(
          animation: _controller,
          builder: (context, _) {
            final t = reduceMotion ? 0.18 : _controller.value;
            final driftX = reduceMotion
                ? 0.0
                : math.sin(t * math.pi * 2) * (isWideWeb ? 5.0 : 2.4);
            final driftY =
                reduceMotion ? 0.0 : math.sin(t * math.pi * 2 + 1.4) * 2.5;

            return Stack(
              fit: StackFit.expand,
              children: [
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 700),
                  child: _videoReady
                      ? _CoverVideo(
                          key: const ValueKey('login-background-video'),
                          controller: _videoController,
                        )
                      : Transform.translate(
                          key: const ValueKey('login-background-fallback'),
                          offset: Offset(driftX, driftY),
                          child: Transform.scale(
                            scale: 1.025,
                            child: Image.asset(
                              isWideWeb
                                  ? 'assets/images/auth/'
                                      'campus_night_landscape.png'
                                  : 'assets/images/auth/'
                                      'campus_night_portrait.png',
                              fit: BoxFit.cover,
                              alignment: isWideWeb
                                  ? Alignment.center
                                  : Alignment.bottomCenter,
                              filterQuality: FilterQuality.high,
                            ),
                          ),
                        ),
                ),
                DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: isWideWeb
                          ? Alignment.centerLeft
                          : Alignment.topCenter,
                      end: isWideWeb
                          ? Alignment.centerRight
                          : Alignment.bottomCenter,
                      colors: isWideWeb
                          ? const [
                              Color(0x30010717),
                              Color(0x5C010717),
                              Color(0xC4010717),
                            ]
                          : const [
                              Color(0x3D010717),
                              Color(0x52010717),
                              Color(0x42010717),
                            ],
                    ),
                  ),
                ),
                CustomPaint(
                  painter: _AmbientLightPainter(
                    progress: t,
                    animate: !reduceMotion,
                    wide: isWideWeb,
                  ),
                ),
              ],
            );
          },
        );
      },
    );
  }
}

class _CoverVideo extends StatelessWidget {
  const _CoverVideo({super.key, required this.controller});

  final VideoPlayerController controller;

  @override
  Widget build(BuildContext context) {
    final videoSize = controller.value.size;
    if (videoSize.isEmpty) return const ColoredBox(color: _night);

    return SizedBox.expand(
      child: FittedBox(
        fit: BoxFit.cover,
        clipBehavior: Clip.hardEdge,
        child: SizedBox(
          width: videoSize.width,
          height: videoSize.height,
          child: VideoPlayer(controller),
        ),
      ),
    );
  }
}

class _AmbientLightPainter extends CustomPainter {
  const _AmbientLightPainter({
    required this.progress,
    required this.animate,
    required this.wide,
  });

  final double progress;
  final bool animate;
  final bool wide;

  @override
  void paint(Canvas canvas, Size size) {
    final particlePaint = Paint()..style = PaintingStyle.fill;
    final count = wide ? 34 : 24;

    for (var i = 0; i < count; i++) {
      final baseX = _fraction(math.sin(i * 91.73) * 817.31);
      final baseY = _fraction(math.cos(i * 47.21) * 631.17) * 0.72;
      final speed = 0.012 + (i % 5) * 0.006;
      final x = _fraction(baseX + progress * speed);
      final y = _fraction(
        baseY + (animate ? math.sin(progress * math.pi * 2 + i) * 0.012 : 0),
      );
      final pulse = animate
          ? 0.42 + math.sin(progress * math.pi * 4 + i * 0.8).abs() * 0.45
          : 0.58;
      particlePaint.color =
          (i % 7 == 0 ? _cyan : Colors.white).withValues(alpha: 0.10 * pulse);
      canvas.drawCircle(
        Offset(x * size.width, y * size.height),
        0.8 + (i % 3) * 0.45,
        particlePaint,
      );
    }

    final glowCenter = Offset(
      (wide ? 0.36 : 0.5) * size.width +
          (animate ? math.sin(progress * math.pi * 2) * 14 : 0),
      (wide ? 0.72 : 0.84) * size.height,
    );
    final glowPaint = Paint()
      ..shader = RadialGradient(
        colors: [
          _cyan.withValues(alpha: 0.10),
          _blue.withValues(alpha: 0.035),
          Colors.transparent,
        ],
      ).createShader(
        Rect.fromCircle(
          center: glowCenter,
          radius: size.shortestSide * (wide ? 0.42 : 0.62),
        ),
      );
    canvas.drawCircle(
      glowCenter,
      size.shortestSide * (wide ? 0.42 : 0.62),
      glowPaint,
    );
  }

  double _fraction(double value) => value - value.floorToDouble();

  @override
  bool shouldRepaint(covariant _AmbientLightPainter oldDelegate) {
    return oldDelegate.progress != progress ||
        oldDelegate.animate != animate ||
        oldDelegate.wide != wide;
  }
}
