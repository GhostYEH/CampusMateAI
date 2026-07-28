import '../../../data/models/models.dart';
import '../../../data/services/api/api_client.dart';
import '../../../data/services/service_interfaces.dart';

/// Mock 任务拆解服务 — 本地规则化拆解,标注 mode=rule_fallback。
///
/// 与后端 [ApiTaskBreakdownService] 实现同一接口,可在 Mock 模式下无缝替换。
/// 输出与后端规则化降级路径一致的结构化步骤(对齐
/// `backend/app/services/task_breakdown_service.py::_build_rule_steps`)。
///
/// 科学边界:
/// - 输出步骤只涉及可观察的学习/事务动作,不进行心理诊断或情绪判断。
/// - 涉及校园政策(申请/截止/材料/办理/学时/奖学金等)的步骤标注
///   is_policy_step=true,并提示用户咨询辅导员或查阅官方资料。
/// - Mock 模式下不调用真实 LLM,始终使用规则化拆解。
class MockTaskBreakdownService implements TaskBreakdownService {
  MockTaskBreakdownService();

  /// 政策关键词(与后端 POLICY_KEYWORDS 对齐)。
  static const List<String> policyKeywords = [
    '申请',
    '截止',
    '截止时间',
    '办理',
    '材料',
    '证明',
    '学时',
    '奖学金',
    '助学金',
    '贷款',
    '补办',
    '注册',
    '报到',
    '选课',
    '退课',
    '请假',
    '休学',
    '复学',
    '转专业',
    '保研',
    '考研',
    '推免',
    '实习',
    '实践',
    '社会实践',
    '综合测评',
    '综测',
    '学分',
    '补考',
    '重修',
    '毕业',
    '学位',
    '论文',
    '答辩',
    '校园卡',
    '宿舍',
    '住宿',
    '学籍',
    '档案',
    '户口',
    '体检',
    '保险',
  ];

  /// 学习类关键词(用于规则化拆解判断)。
  static const List<String> studyKeywords = [
    '复习',
    '预习',
    '学习',
    '做作业',
    '完成作业',
    '刷题',
    '练习',
    '阅读',
    '看',
    '整理',
    '背诵',
    '记忆',
    '理解',
    '掌握',
    '总结',
    '写',
    '编程',
    '编码',
    '实现',
    '调试',
    '测试',
    '报告',
    '实验',
    '项目',
    '课程',
  ];

  bool _containsAny(String text, Iterable<String> keywords) {
    if (text.isEmpty) return false;
    return keywords.any((kw) => text.contains(kw));
  }

  bool _isPolicyIntent(String goal) => _containsAny(goal, policyKeywords);
  bool _isStudyIntent(String goal) => _containsAny(goal, studyKeywords);

  @override
  Future<TaskBreakdownResponse> breakdown(
    TaskBreakdownRequest request,
  ) async {
    // 模拟后端处理延迟
    await Future.delayed(const Duration(milliseconds: 320));

    if (request.isEmpty) {
      throw const ApiException(
        code: 'VALIDATION_FAILED',
        message: 'task_id 与 goal 不能同时为空',
      );
    }

    final warnings = <String>[];
    String? relatedTaskId;
    String? relatedTaskTitle;
    final String goalText = (request.goal ?? '').trim();

    // task_id 在 Mock 模式下无法解析为后端任务,记录 warning
    if (request.taskId != null && request.taskId!.isNotEmpty) {
      warnings.add('Mock 模式:task_id=${request.taskId} 未对接后端任务,改用 goal 拆解');
      relatedTaskId = request.taskId;
      // Mock 模式下不知道任务标题,留空
      relatedTaskTitle = null;
    }

    if (goalText.isEmpty) {
      // task_id 解析失败且无 goal
      throw const ApiException(
        code: 'VALIDATION_FAILED',
        message: 'Mock 模式下 task_id 无法解析,且未提供 goal',
      );
    }

    final isPolicy = _isPolicyIntent(goalText);
    final isStudy = _isStudyIntent(goalText) || !isPolicy;

    if (isPolicy) {
      // Mock 模式下无知识库,记录 warning
      warnings.add('Mock 模式:目标涉及校园政策但未接入知识库,政策步骤以提示性建议为主');
    }

    final steps = _buildRuleSteps(
      goalText,
      isPolicy: isPolicy,
      isStudy: isStudy,
    );

    return TaskBreakdownResponse(
      mode: TaskBreakdownMode.ruleFallback,
      steps: steps,
      goal: goalText,
      relatedTaskId: relatedTaskId,
      relatedTaskTitle: relatedTaskTitle,
      warnings: warnings,
    );
  }

  List<TaskBreakdownStep> _buildRuleSteps(
    String goal, {
    required bool isPolicy,
    required bool isStudy,
  }) {
    final steps = <TaskBreakdownStep>[];

    // 1. 明确目标
    steps.add(
      TaskBreakdownStep(
        stepNumber: 1,
        title: '明确目标与范围',
        description:
            '用一句话写下本次目标: ${goal.length > 80 ? goal.substring(0, 80) : goal}。'
            '明确产出物(笔记/代码/报告/答案)与完成标准。',
        estimatedMinutes: 10,
        dependencies: const [],
        completionCriteria: '已写下目标与产出物描述,并能口头复述完成标准',
        isPolicyStep: false,
      ),
    );

    // 2. 准备资源(学习类)
    if (isStudy) {
      steps.add(
        const TaskBreakdownStep(
          stepNumber: 2,
          title: '准备学习资源',
          description: '整理需要的教材、课件、笔记工具或代码环境,确认网络/账号/软件就绪。',
          estimatedMinutes: 15,
          dependencies: [1],
          completionCriteria: '所需资源已打开或下载,可立即开始学习',
          isPolicyStep: false,
        ),
      );
    }

    // 3. 政策查阅
    if (isPolicy) {
      steps.add(
        TaskBreakdownStep(
          stepNumber: steps.length + 1,
          title: '查阅政策资料 / 咨询辅导员',
          description: '本目标涉及校园政策相关事项。Mock 模式下未接入知识库,'
              '建议咨询辅导员或相关负责老师,或查阅学校官方通知渠道'
              '(教务系统/学院公众号)。',
          estimatedMinutes: 20,
          dependencies: const [1],
          completionCriteria: '已向辅导员或相关部门确认本事项的具体要求',
          isPolicyStep: true,
        ),
      );
    }

    // 4. 主执行步骤
    if (isStudy) {
      steps.add(
        TaskBreakdownStep(
          stepNumber: steps.length + 1,
          title: '分块执行核心任务',
          description: '将核心任务拆成 2~3 个 25~40 分钟的小块,'
              '每块专注单一子任务,完成一块后短暂休息。',
          estimatedMinutes: 80,
          dependencies: [isStudy ? 2 : 1],
          completionCriteria: '所有子任务块均已完成,产出物可见',
          isPolicyStep: false,
        ),
      );
    }

    // 5. 自测
    final lastDeps = [steps.last.stepNumber];
    steps.add(
      TaskBreakdownStep(
        stepNumber: steps.length + 1,
        title: '自测与查漏补缺',
        description: '用 2~3 个问题自测目标达成度,或对照完成标准逐项检查产出物。',
        estimatedMinutes: 15,
        dependencies: lastDeps,
        completionCriteria: '能回答自测问题或所有检查项均已勾选',
        isPolicyStep: false,
      ),
    );

    // 6. 整理产出
    steps.add(
      TaskBreakdownStep(
        stepNumber: steps.length + 1,
        title: '整理产出与归档',
        description: '把笔记/代码/报告/截图归档到对应课程或事项目录,'
            '记录本次未完成的疑问(供下次或咨询时使用)。',
        estimatedMinutes: 10,
        dependencies: [steps.last.stepNumber],
        completionCriteria: '产出物已归档,疑问清单已记录',
        isPolicyStep: false,
      ),
    );

    return steps;
  }
}
