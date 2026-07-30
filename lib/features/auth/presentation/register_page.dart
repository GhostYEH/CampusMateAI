import 'dart:async';
import 'dart:math' as math;
import 'dart:ui';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../app/providers/auth_providers.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../core/widgets/state_views.dart';
import '../../../data/models/auth.dart';
import '../../../data/models/user.dart';
import '../../../data/services/api/api_client.dart';

// 与登录页共享的视觉常量(刻意保持一致,避免注册/登录视觉割裂)。
const _night = Color(0xFF020A1D);
const _panel = Color(0x780A1931);
const _line = Color(0x52D6ECFF);
const _textPrimary = Color(0xFFF5F8FF);
const _textSecondary = Color(0xFF9BADCA);
const _cyan = Color(0xFF63D9EA);

/// 公开注册页面 — 复用登录页的夜间校园视觉语言。
///
/// 设计:
/// - 仅允许注册 student / teacher 角色(admin 必须由管理员创建)。
/// - 注册成功后不自动登录,跳回登录页让用户使用新账号登录。
/// - 表单实时校验:用户名/密码长度、两次密码一致、角色与学号/工号一致。
/// - 支持「减少动态效果」无障碍设置。
class RegisterPage extends ConsumerStatefulWidget {
  const RegisterPage({super.key, this.prefilledUsername});

  /// 可选:从登录页跳转时预填的用户名。
  final String? prefilledUsername;

  @override
  ConsumerState<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends ConsumerState<RegisterPage> {
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();
  final _displayNameController = TextEditingController();
  final _studentNumberController = TextEditingController();
  final _teacherNumberController = TextEditingController();
  final _collegeController = TextEditingController();
  final _majorController = TextEditingController();
  final _gradeController = TextEditingController();

  final _usernameFocus = FocusNode();
  final _passwordFocus = FocusNode();
  final _confirmFocus = FocusNode();

  bool _obscurePassword = true;
  bool _obscureConfirm = true;
  UserRole _selectedRole = UserRole.student;
  bool _isSubmitting = false;
  String? _errorMessage;
  String? _successMessage;

  @override
  void initState() {
    super.initState();
    if (widget.prefilledUsername != null &&
        widget.prefilledUsername!.isNotEmpty) {
      _usernameController.text = widget.prefilledUsername!;
    }
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    _displayNameController.dispose();
    _studentNumberController.dispose();
    _teacherNumberController.dispose();
    _collegeController.dispose();
    _majorController.dispose();
    _gradeController.dispose();
    _usernameFocus.dispose();
    _passwordFocus.dispose();
    _confirmFocus.dispose();
    super.dispose();
  }

  /// 校验表单并返回错误提示(null 表示通过)。
  String? _validateForm() {
    final username = _usernameController.text.trim();
    final password = _passwordController.text;
    final confirm = _confirmPasswordController.text;

    if (username.isEmpty) return '请输入用户名。';
    if (username.length < 3) return '用户名至少 3 个字符。';
    if (!RegExp(r'^[a-zA-Z0-9_]+$').hasMatch(username)) {
      return '用户名仅允许字母、数字和下划线。';
    }
    if (password.isEmpty) return '请输入密码。';
    if (password.length < 8) return '密码至少 8 个字符。';
    if (password != confirm) return '两次输入的密码不一致。';

    // 角色一致性校验
    if (_selectedRole == UserRole.student &&
        _teacherNumberController.text.trim().isNotEmpty) {
      return '学生角色不应填写工号。';
    }
    if (_selectedRole == UserRole.teacher &&
        _studentNumberController.text.trim().isNotEmpty) {
      return '教师角色不应填写学号。';
    }

    return null;
  }

  Future<void> _submit() async {
    if (_isSubmitting) return;

    final validationError = _validateForm();
    if (validationError != null) {
      setState(() => _errorMessage = validationError);
      return;
    }

    setState(() {
      _errorMessage = null;
      _isSubmitting = true;
    });
    FocusScope.of(context).unfocus();

    try {
      final credentials = RegisterCredentials(
        username: _usernameController.text.trim(),
        password: _passwordController.text,
        role: _selectedRole,
        displayName: _displayNameController.text.trim().isEmpty
            ? null
            : _displayNameController.text.trim(),
        studentNumber: _studentNumberController.text.trim().isEmpty
            ? null
            : _studentNumberController.text.trim(),
        teacherNumber: _teacherNumberController.text.trim().isEmpty
            ? null
            : _teacherNumberController.text.trim(),
        college: _collegeController.text.trim().isEmpty
            ? null
            : _collegeController.text.trim(),
        major: _majorController.text.trim().isEmpty
            ? null
            : _majorController.text.trim(),
        grade: _gradeController.text.trim().isEmpty
            ? null
            : _gradeController.text.trim(),
      );

      await ref.read(authNotifierProvider.notifier).register(credentials);

      if (!mounted) return;
      // 注册成功 → 跳回登录页并提示
      setState(() {
        _isSubmitting = false;
        _successMessage = '注册成功,请使用新账号登录。';
      });
      // 短暂展示成功状态后跳转
      await Future.delayed(const Duration(milliseconds: 600));
      if (!mounted) return;
      context.go('/login', extra: '注册成功,请使用新账号登录。');
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _isSubmitting = false;
        _errorMessage = _friendlyMessageFromApiException(e);
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _isSubmitting = false;
        _errorMessage = '注册失败,请稍后重试。';
      });
    }
  }

  /// 把后端错误码映射为用户友好文案。
  String _friendlyMessageFromApiException(ApiException e) {
    switch (e.code.toUpperCase()) {
      case 'USERNAME_EXISTS':
        return '该用户名已被注册,请更换后重试。';
      case 'STUDENT_NUMBER_EXISTS':
        return '该学号已存在,请核对后重试。';
      case 'TEACHER_NUMBER_EXISTS':
        return '该工号已存在,请核对后重试。';
      case 'VALIDATION_FAILED':
        return e.message.isNotEmpty ? e.message : '提交的数据校验未通过。';
      default:
        return e.message.isNotEmpty ? e.message : '注册失败,请稍后重试。';
    }
  }

  void _goBackToLogin() {
    if (_isSubmitting) return;
    context.go('/login');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _night,
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final useWebLayout = kIsWeb && constraints.maxWidth >= 900;
            final form = _buildForm();
            if (useWebLayout) {
              return _WebRegisterLayout(form: form);
            }
            return _MobileRegisterLayout(
              compact: constraints.maxHeight < 700,
              form: form,
            );
          },
        ),
      ),
    );
  }

  Widget _buildForm() {
    return _RegisterPanel(
      usernameController: _usernameController,
      passwordController: _passwordController,
      confirmPasswordController: _confirmPasswordController,
      displayNameController: _displayNameController,
      studentNumberController: _studentNumberController,
      teacherNumberController: _teacherNumberController,
      collegeController: _collegeController,
      majorController: _majorController,
      gradeController: _gradeController,
      usernameFocus: _usernameFocus,
      passwordFocus: _passwordFocus,
      confirmFocus: _confirmFocus,
      obscurePassword: _obscurePassword,
      obscureConfirm: _obscureConfirm,
      selectedRole: _selectedRole,
      isSubmitting: _isSubmitting,
      errorMessage: _errorMessage,
      successMessage: _successMessage,
      onToggleObscurePassword: () {
        setState(() => _obscurePassword = !_obscurePassword);
      },
      onToggleObscureConfirm: () {
        setState(() => _obscureConfirm = !_obscureConfirm);
      },
      onRoleChanged: (role) {
        setState(() {
          _selectedRole = role;
          // 切换角色时清空对方的号码字段,避免一致性校验失败
          if (role == UserRole.student) {
            _teacherNumberController.clear();
          } else {
            _studentNumberController.clear();
          }
        });
      },
      onSubmit: _submit,
      onBackToLogin: _goBackToLogin,
    );
  }
}

// ===== 布局 =====

class _MobileRegisterLayout extends StatelessWidget {
  const _MobileRegisterLayout({
    required this.compact,
    required this.form,
  });

  final bool compact;
  final Widget form;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(20, compact ? 12 : 24, 20, 24),
      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 430),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const StaggeredEnter(child: _RegisterHeader(compact: true)),
              SizedBox(height: compact ? 14 : 22),
              StaggeredEnter(
                delay: const Duration(milliseconds: 100),
                child: form,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _WebRegisterLayout extends StatelessWidget {
  const _WebRegisterLayout({required this.form});

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
                      StaggeredEnter(child: _RegisterHeader()),
                      SizedBox(height: 28),
                      StaggeredEnter(
                        delay: Duration(milliseconds: 120),
                        child: _WebWelcome(),
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

class _RegisterHeader extends StatelessWidget {
  const _RegisterHeader({this.compact = false});

  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: compact ? MainAxisAlignment.center : MainAxisAlignment.start,
      children: [
        Container(
          width: compact ? 44 : 54,
          height: compact ? 44 : 54,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(compact ? 13 : 16),
            gradient: const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFF5B8DFF), Color(0xFF2555C7)],
            ),
            border: Border.all(color: Colors.white.withValues(alpha: 0.18)),
          ),
          child: Icon(
            Icons.person_add_rounded,
            color: Colors.white,
            size: compact ? 22 : 28,
          ),
        ),
        const SizedBox(width: 12),
        Column(
          crossAxisAlignment: compact ? CrossAxisAlignment.center : CrossAxisAlignment.start,
          children: [
            Text(
              '创建账号',
              style: AppTypography.headline.copyWith(
                color: _textPrimary,
                fontSize: compact ? 20 : 24,
                letterSpacing: -0.5,
              ),
            ),
            const SizedBox(height: 3),
            Text(
              '加入 CampusMate AI,开启智能校园生活',
              style: AppTypography.caption.copyWith(
                color: _textSecondary,
                letterSpacing: 0.8,
              ),
            ),
          ],
        ),
      ],
    );
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
            '欢迎加入,\n和校园里的一切事务说清楚。',
            style: AppTypography.display.copyWith(
              color: _textPrimary,
              fontSize: 38,
              height: 1.22,
              letterSpacing: -1.1,
            ),
          ),
          const SizedBox(height: 16),
          Text(
            '注册后即可使用通知整理、任务协同、学习陪伴和 AI 导员。',
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

// ===== 表单面板 =====

class _RegisterPanel extends StatelessWidget {
  const _RegisterPanel({
    required this.usernameController,
    required this.passwordController,
    required this.confirmPasswordController,
    required this.displayNameController,
    required this.studentNumberController,
    required this.teacherNumberController,
    required this.collegeController,
    required this.majorController,
    required this.gradeController,
    required this.usernameFocus,
    required this.passwordFocus,
    required this.confirmFocus,
    required this.obscurePassword,
    required this.obscureConfirm,
    required this.selectedRole,
    required this.isSubmitting,
    required this.errorMessage,
    required this.successMessage,
    required this.onToggleObscurePassword,
    required this.onToggleObscureConfirm,
    required this.onRoleChanged,
    required this.onSubmit,
    required this.onBackToLogin,
  });

  final TextEditingController usernameController;
  final TextEditingController passwordController;
  final TextEditingController confirmPasswordController;
  final TextEditingController displayNameController;
  final TextEditingController studentNumberController;
  final TextEditingController teacherNumberController;
  final TextEditingController collegeController;
  final TextEditingController majorController;
  final TextEditingController gradeController;
  final FocusNode usernameFocus;
  final FocusNode passwordFocus;
  final FocusNode confirmFocus;
  final bool obscurePassword;
  final bool obscureConfirm;
  final UserRole selectedRole;
  final bool isSubmitting;
  final String? errorMessage;
  final String? successMessage;
  final VoidCallback onToggleObscurePassword;
  final VoidCallback onToggleObscureConfirm;
  final ValueChanged<UserRole> onRoleChanged;
  final VoidCallback onSubmit;
  final VoidCallback onBackToLogin;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(26),
      child: BackdropFilter(
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
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                '填写信息',
                style: AppTypography.title.copyWith(
                  color: _textPrimary,
                  fontSize: 18,
                ),
              ),
              const SizedBox(height: 3),
              Text(
                '仅限学生 / 教师注册,管理员由学校创建',
                style: AppTypography.caption.copyWith(color: _textSecondary),
              ),
              if (errorMessage != null) ...[
                const SizedBox(height: 14),
                _Banner(
                  message: errorMessage!,
                  color: const Color(0xFFFF9B98),
                  bgColor: const Color(0x26FF5555),
                  icon: Icons.error_outline_rounded,
                ),
              ],
              if (successMessage != null) ...[
                const SizedBox(height: 14),
                _Banner(
                  message: successMessage!,
                  color: const Color(0xFF9FE6B6),
                  bgColor: const Color(0x2633CC66),
                  icon: Icons.check_circle_outline_rounded,
                ),
              ],
              const SizedBox(height: 18),
              // 角色选择
              _RoleSelector(
                selectedRole: selectedRole,
                onChanged: onRoleChanged,
                enabled: !isSubmitting,
              ),
              const SizedBox(height: 15),
              _NightTextField(
                controller: usernameController,
                focusNode: usernameFocus,
                label: '用户名',
                hint: '3-64 字符,字母 / 数字 / 下划线',
                prefixIcon: Icons.alternate_email_rounded,
                textInputAction: TextInputAction.next,
                enabled: !isSubmitting,
              ),
              const SizedBox(height: 12),
              _NightTextField(
                controller: displayNameController,
                label: '昵称(选填)',
                hint: '展示给其他人的名字',
                prefixIcon: Icons.badge_outlined,
                textInputAction: TextInputAction.next,
                enabled: !isSubmitting,
              ),
              const SizedBox(height: 12),
              _NightTextField(
                controller: passwordController,
                focusNode: passwordFocus,
                label: '密码',
                hint: '至少 8 个字符',
                prefixIcon: Icons.lock_outline_rounded,
                obscure: obscurePassword,
                enabled: !isSubmitting,
                suffix: IconButton(
                  tooltip: obscurePassword ? '显示密码' : '隐藏密码',
                  icon: Icon(
                    obscurePassword
                        ? Icons.visibility_off_outlined
                        : Icons.visibility_outlined,
                    size: 20,
                    color: _textSecondary,
                  ),
                  onPressed: onToggleObscurePassword,
                ),
                textInputAction: TextInputAction.next,
              ),
              const SizedBox(height: 12),
              _NightTextField(
                controller: confirmPasswordController,
                focusNode: confirmFocus,
                label: '确认密码',
                hint: '再次输入密码',
                prefixIcon: Icons.lock_reset_outlined,
                obscure: obscureConfirm,
                enabled: !isSubmitting,
                suffix: IconButton(
                  tooltip: obscureConfirm ? '显示密码' : '隐藏密码',
                  icon: Icon(
                    obscureConfirm
                        ? Icons.visibility_off_outlined
                        : Icons.visibility_outlined,
                    size: 20,
                    color: _textSecondary,
                  ),
                  onPressed: onToggleObscureConfirm,
                ),
                textInputAction: TextInputAction.next,
              ),
              const SizedBox(height: 12),
              // 角色相关字段
              if (selectedRole == UserRole.student) ...[
                _NightTextField(
                  controller: studentNumberController,
                  label: '学号(选填)',
                  hint: '如 S20240001',
                  prefixIcon: Icons.numbers_outlined,
                  textInputAction: TextInputAction.next,
                  enabled: !isSubmitting,
                ),
                const SizedBox(height: 12),
              ] else if (selectedRole == UserRole.teacher) ...[
                _NightTextField(
                  controller: teacherNumberController,
                  label: '工号(选填)',
                  hint: '如 T20240001',
                  prefixIcon: Icons.numbers_outlined,
                  textInputAction: TextInputAction.next,
                  enabled: !isSubmitting,
                ),
                const SizedBox(height: 12),
              ],
              // 学生常用字段(教师也可填学院)
              _NightTextField(
                controller: collegeController,
                label: selectedRole == UserRole.student ? '学院(选填)' : '院系(选填)',
                hint: '如 信息工程学院',
                prefixIcon: Icons.account_balance_outlined,
                textInputAction: TextInputAction.next,
                enabled: !isSubmitting,
              ),
              const SizedBox(height: 12),
              if (selectedRole == UserRole.student) ...[
                _NightTextField(
                  controller: majorController,
                  label: '专业(选填)',
                  hint: '如 计算机科学与技术',
                  prefixIcon: Icons.school_outlined,
                  textInputAction: TextInputAction.next,
                  enabled: !isSubmitting,
                ),
                const SizedBox(height: 12),
                _NightTextField(
                  controller: gradeController,
                  label: '年级(选填)',
                  hint: '如 2024',
                  prefixIcon: Icons.calendar_today_outlined,
                  textInputAction: TextInputAction.done,
                  enabled: !isSubmitting,
                ),
                const SizedBox(height: 8),
              ],
              const SizedBox(height: 18),
              _PrismaticRegisterButton(
                isLoading: isSubmitting,
                onPressed: onSubmit,
              ),
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    '已有账号?',
                    style: AppTypography.caption.copyWith(
                      color: _textSecondary,
                    ),
                  ),
                  TextButton(
                    onPressed: isSubmitting ? null : onBackToLogin,
                    style: TextButton.styleFrom(
                      foregroundColor: _cyan,
                      padding: const EdgeInsets.symmetric(horizontal: 6),
                      minimumSize: const Size(0, 36),
                    ),
                    child: const Text('返回登录'),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              Text(
                '注册即表示同意遵守《校园网络安全规范》',
                textAlign: TextAlign.center,
                style: AppTypography.overline.copyWith(
                  color: _textSecondary.withValues(alpha: 0.78),
                  fontWeight: FontWeight.w400,
                  letterSpacing: 0,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ===== 角色选择器 =====

class _RoleSelector extends StatelessWidget {
  const _RoleSelector({
    required this.selectedRole,
    required this.onChanged,
    required this.enabled,
  });

  final UserRole selectedRole;
  final ValueChanged<UserRole> onChanged;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _RoleChip(
            label: '学生',
            icon: Icons.school_rounded,
            selected: selectedRole == UserRole.student,
            enabled: enabled,
            onTap: () => onChanged(UserRole.student),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: _RoleChip(
            label: '教师',
            icon: Icons.co_present_rounded,
            selected: selectedRole == UserRole.teacher,
            enabled: enabled,
            onTap: () => onChanged(UserRole.teacher),
          ),
        ),
      ],
    );
  }
}

class _RoleChip extends StatelessWidget {
  const _RoleChip({
    required this.label,
    required this.icon,
    required this.selected,
    required this.enabled,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = selected ? _cyan : _textSecondary;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: enabled ? onTap : null,
        borderRadius: BorderRadius.circular(12),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            color: selected
                ? _cyan.withValues(alpha: 0.10)
                : const Color(0x52101E37),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: selected ? _cyan : _line,
              width: selected ? 1.4 : 1,
            ),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, size: 18, color: color),
              const SizedBox(width: 8),
              Text(
                label,
                style: AppTypography.label.copyWith(
                  color: selected ? _textPrimary : color,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ===== 夜间主题文本框 =====

class _NightTextField extends StatelessWidget {
  const _NightTextField({
    required this.controller,
    required this.label,
    required this.hint,
    required this.prefixIcon,
    this.focusNode,
    this.obscure = false,
    this.suffix,
    this.textInputAction,
    this.enabled = true,
  });

  final TextEditingController controller;
  final FocusNode? focusNode;
  final String label;
  final String hint;
  final IconData prefixIcon;
  final bool obscure;
  final Widget? suffix;
  final TextInputAction? textInputAction;
  final bool enabled;

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
          enabled: enabled,
          textInputAction: textInputAction,
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
            disabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide(color: _line.withValues(alpha: 0.5)),
            ),
          ),
        ),
      ],
    );
  }
}

// ===== 错误 / 成功横幅 =====

class _Banner extends StatelessWidget {
  const _Banner({
    required this.message,
    required this.color,
    required this.bgColor,
    required this.icon,
  });

  final String message;
  final Color color;
  final Color bgColor;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.42)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 18, color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: AppTypography.caption.copyWith(color: color),
            ),
          ),
        ],
      ),
    );
  }
}

// ===== 注册按钮(彩虹渐变,与登录页一致的设计语言) =====

class _PrismaticRegisterButton extends ConsumerStatefulWidget {
  const _PrismaticRegisterButton({
    required this.isLoading,
    required this.onPressed,
  });

  final bool isLoading;
  final VoidCallback onPressed;

  @override
  ConsumerState<_PrismaticRegisterButton> createState() =>
      _PrismaticRegisterButtonState();
}

class _PrismaticRegisterButtonState
    extends ConsumerState<_PrismaticRegisterButton>
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
            : const Icon(Icons.person_add_rounded, size: 20),
        label: Text(
          widget.isLoading ? '注册中...' : '注册',
          style: AppTypography.bodyStrong.copyWith(color: Colors.white),
        ),
      ),
    );
  }
}
