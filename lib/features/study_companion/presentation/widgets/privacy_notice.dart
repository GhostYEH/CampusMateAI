import 'package:flutter/material.dart';

/// 隐私说明对话框 — 强调表情识别本地化、不进行心理诊断。
///
/// 体现科学边界:不诊断、不替代专业心理咨询。
void showStudyPrivacyDialog(BuildContext context) {
  showDialog<void>(
    context: context,
    builder: (context) => AlertDialog(
      title: const Text('隐私说明'),
      content: const Text(
        '• 表情识别完全在本地进行,不会上传任何图像或视频。\n'
        '• 仅识别可观察到的面部表情,不进行心理诊断。\n'
        '• 识别结果仅供学习状态辅助参考,不代表情绪判定。\n'
        '• 你可以随时在"我的"中关闭表情识别。\n'
        '• 疲劳判断结合学习时长,不等同于表情类别。',
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
