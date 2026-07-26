import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:markdown/markdown.dart' as md;

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';

/// AI 导员回答的 Markdown 渲染器。
///
/// 设计要点:
/// - 流式输出阶段由父组件自行展示纯文本 + 光标,避免半截 markdown 抖动;
///   流式结束后切换为本组件,完成 Markdown 排版。
/// - 样式严格遵循 AppColors / AppTypography,与"晨曦校园"配色一致。
/// - 不渲染图片、不渲染 HTML,避免模型意外输出带来的安全/布局问题。
class CounselorMarkdownBody extends StatelessWidget {
  const CounselorMarkdownBody({
    super.key,
    required this.content,
    this.onTapLink,
  });

  final String content;

  /// 链接点击回调(用于后续接入"打开资料"等动作)。
  final void Function(String url)? onTapLink;

  @override
  Widget build(BuildContext context) {
    return MarkdownBody(
      data: content,
      selectable: false,
      fitContent: true,
      shrinkWrap: true,
      onTapLink: onTapLink == null
          ? null
          : (text, href, title) {
              if (href != null && href.isNotEmpty) {
                onTapLink!(href);
              }
            },
      extensionSet: md.ExtensionSet.none,
      styleSheet: _styleSheet,
    );
  }

  MarkdownStyleSheet get _styleSheet => MarkdownStyleSheet(
        p: AppTypography.body.copyWith(
          color: AppColors.textPrimary,
          height: 1.55,
        ),
        h2: AppTypography.subtitle.copyWith(
          color: AppColors.textPrimary,
          fontSize: 15.5,
          fontWeight: FontWeight.w700,
          height: 1.35,
        ),
        h2Padding: const EdgeInsets.only(top: 8, bottom: 4),
        h3: AppTypography.bodyStrong.copyWith(
          color: AppColors.textPrimary,
        ),
        h3Padding: const EdgeInsets.only(top: 6, bottom: 3),
        listIndent: 20,
        listBullet: AppTypography.body.copyWith(
          color: AppColors.primary,
          fontWeight: FontWeight.w700,
          fontSize: 13,
        ),
        listBulletPadding: const EdgeInsets.only(right: 6),
        orderedListAlign: WrapAlignment.start,
        unorderedListAlign: WrapAlignment.start,
        strong: AppTypography.bodyStrong.copyWith(
          color: AppColors.textPrimary,
          fontWeight: FontWeight.w700,
        ),
        em: AppTypography.body.copyWith(
          fontStyle: FontStyle.italic,
          color: AppColors.textSecondary,
        ),
        blockSpacing: 6,
        blockquote: AppTypography.body.copyWith(
          color: AppColors.textSecondary,
          fontStyle: FontStyle.italic,
        ),
        blockquoteDecoration: const BoxDecoration(
          color: AppColors.bgSunken,
          borderRadius: BorderRadius.all(Radius.circular(AppRadius.xs)),
          border: Border(
            left: BorderSide(
              color: AppColors.primarySubtle,
              width: 3,
            ),
          ),
        ),
        code: AppTypography.caption.copyWith(
          color: AppColors.primary,
          backgroundColor: AppColors.primarySubtle,
          fontWeight: FontWeight.w600,
          fontSize: 12.5,
        ),
        codeblockPadding: const EdgeInsets.symmetric(
          horizontal: 10,
          vertical: 8,
        ),
        codeblockDecoration: const BoxDecoration(
          color: AppColors.bgSunken,
          borderRadius: BorderRadius.all(Radius.circular(AppRadius.sm)),
          border: Border.fromBorderSide(
            BorderSide(color: AppColors.border, width: 0.6),
          ),
        ),
        horizontalRuleDecoration: const BoxDecoration(
          border: Border(
            top: BorderSide(
              color: AppColors.border,
              width: 0.6,
            ),
          ),
        ),
        a: AppTypography.body.copyWith(
          color: AppColors.primary,
          decoration: TextDecoration.underline,
          decorationColor: AppColors.primary,
        ),
      );
}
