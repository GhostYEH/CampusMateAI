import 'dart:async';
import 'dart:math';

import '../../data/models/models.dart';
import '../../data/services/api/api_client.dart';
import '../../data/services/expression_service_status.dart';
import '../../data/services/service_interfaces.dart';
import '../mock_data/mock_data.dart';
import 'expression_smoother.dart';

/// Mock 通知提取服务 — 模拟分步骤处理,基于关键词规则提取。
///
/// 真实实现将通过 FastAPI 调用 LLM + 规则。Mock 阶段使用关键词匹配,
/// 明确标注来源为"模拟提取"。
class MockNotificationExtractionService
    implements NotificationExtractionService {
  @override
  Future<ExtractedNotice> extract(
    String rawNotice, {
    void Function(ExtractionStep step)? onProgress,
  }) async {
    final steps = [
      const ExtractionStep(label: '正在识别通知类型', order: 0),
      const ExtractionStep(label: '提取任务名称与面向对象', order: 1),
      const ExtractionStep(label: '解析截止时间', order: 2),
      const ExtractionStep(label: '识别所需材料', order: 3),
      const ExtractionStep(label: '判断提交方式与地点', order: 4),
      const ExtractionStep(label: '评估重要程度', order: 5),
    ];

    for (final step in steps) {
      onProgress?.call(step);
      await Future.delayed(const Duration(milliseconds: 360));
    }

    return _ruleExtract(rawNotice);
  }

  ExtractedNotice _ruleExtract(String raw) {
    final text = raw.replaceAll(RegExp(r'\s+'), '');

    // 任务名称
    String taskName = '校园通知待办';
    if (text.contains('实践') && text.contains('申请')) {
      taskName = '提交实践申请';
    } else if (text.contains('综合测评')) {
      taskName = '完成综合测评材料汇总';
    } else if (text.contains('奖学金')) {
      taskName = '提交奖学金申请';
    } else if (text.contains('选课') || text.contains('补退选')) {
      taskName = '完成选课补退选';
    } else if (text.contains('报名')) {
      taskName = '完成活动报名';
    }

    // 面向对象
    String? audience;
    final gradeMatch = RegExp(r'(\d{4}级)').firstMatch(text);
    if (gradeMatch != null) audience = gradeMatch.group(1);
    if (text.contains('各班级')) audience = audience ?? '各班级';

    // 截止时间
    DateTime? deadline;
    final now = DateTime.now();
    if (text.contains('本周五')) {
      deadline = _nextWeekday(now, DateTime.friday);
    } else if (text.contains('下周一')) {
      deadline = _nextWeekday(now, DateTime.monday);
    }
    final dateMatch = RegExp(r'(\d{1,2})月(\d{1,2})日').firstMatch(text);
    if (dateMatch != null) {
      final month = int.parse(dateMatch.group(1)!);
      final day = int.parse(dateMatch.group(2)!);
      var year = now.year;
      if (month < now.month || (month == now.month && day < now.day)) {
        year++;
      }
      deadline = DateTime(year, month, day, 23, 59);
    }

    // 材料
    final materials = <TaskMaterial>[];
    if (text.contains('申请表')) {
      materials.add(TaskMaterial(id: 'em_${materials.length}', name: '申请表'));
    }
    if (text.contains('证明材料') || text.contains('证明')) {
      materials.add(TaskMaterial(id: 'em_${materials.length}', name: '证明材料'));
    }
    if (text.contains('总结报告') || text.contains('报告')) {
      materials.add(TaskMaterial(id: 'em_${materials.length}', name: '总结报告'));
    }
    if (text.contains('成绩单')) {
      materials.add(TaskMaterial(id: 'em_${materials.length}', name: '成绩单'));
    }
    if (text.contains('个人陈述')) {
      materials.add(TaskMaterial(id: 'em_${materials.length}', name: '个人陈述'));
    }

    // 提交方式与地点
    String? method;
    String? location;
    if (text.contains('纸质版') || text.contains('提交至')) {
      method = '提交纸质版';
    }
    if (text.contains('电子版') || text.contains('发送至')) {
      method = method == null ? '发送电子版' : '$method + 电子版';
    }
    if (text.contains('学生系统') || text.contains('教务系统')) {
      method = method == null ? '系统提交' : '$method / 系统提交';
    }
    final locMatch = RegExp(r'(行政楼\w*|学院办公室|辅导员\w*|教务处)').firstMatch(text);
    if (locMatch != null) location = locMatch.group(1);

    // 重要程度
    var importance = NoticeImportance.normal;
    if (text.contains('紧急') || text.contains('逾期不予受理')) {
      importance = NoticeImportance.urgent;
    } else if (text.contains('评选') || text.contains('汇总')) {
      importance = NoticeImportance.important;
    }

    final confidence = _estimateConfidence(raw);
    return ExtractedNotice(
      taskName: taskName,
      targetAudience: audience,
      deadline: deadline,
      materials: materials,
      submitMethod: method,
      location: location,
      sourceText: raw,
      importance: importance,
      confidence: confidence,
      extractedSteps: const [
        '识别通知类型',
        '提取任务名称',
        '解析截止时间',
        '识别材料清单',
        '判断提交方式',
      ],
    );
  }

  double _estimateConfidence(String raw) {
    if (raw.trim().isEmpty) return 0;
    var score = 0.3;
    if (RegExp(r'\d{1,2}月\d{1,2}日|本周|下周').hasMatch(raw)) score += 0.25;
    if (RegExp(r'申请表|证明|报告|成绩单').hasMatch(raw)) score += 0.2;
    if (RegExp(r'提交至|发送至|系统').hasMatch(raw)) score += 0.15;
    if (RegExp(r'\d{4}级|各班级|同学').hasMatch(raw)) score += 0.1;
    return score.clamp(0.0, 1.0);
  }

  DateTime _nextWeekday(DateTime from, int target) {
    var date = from;
    while (date.weekday != target) {
      date = date.add(const Duration(days: 1));
    }
    return DateTime(date.year, date.month, date.day, 23, 59);
  }

  @override
  Future<MultiExtractResult> extractMulti(
    String rawNotice, {
    void Function(ExtractionStep step)? onProgress,
  }) async {
    final steps = [
      const ExtractionStep(label: '正在识别通知类型', order: 0),
      const ExtractionStep(label: '检测多个独立任务', order: 1),
      const ExtractionStep(label: '解析各任务截止时间', order: 2),
      const ExtractionStep(label: '识别各任务材料', order: 3),
      const ExtractionStep(label: '判断是否需要人工确认', order: 4),
    ];

    for (final step in steps) {
      onProgress?.call(step);
      await Future.delayed(const Duration(milliseconds: 300));
    }

    // Mock 多任务拆分规则:
    // 1. 检测"并于/以及/然后/同时/另外"等连接词 + 多个截止时间
    // 2. 检测多个"X月X日"日期
    final text = rawNotice.replaceAll(RegExp(r'\s+'), '');
    final dateMatches = RegExp(r'(\d{1,2})月(\d{1,2})日').allMatches(text);
    final hasConnector = RegExp(r'并于|以及|然后|同时|另外|其次|接着').hasMatch(text);

    if ((dateMatches.length >= 2 || hasConnector) && dateMatches.isNotEmpty) {
      // 尝试按日期拆分
      final segments = _splitByDates(rawNotice, dateMatches.toList());
      if (segments.length >= 2) {
        final tasks = segments.map((s) => _ruleExtract(s)).toList();
        return MultiExtractResult(
          tasks: tasks,
          splitReason: '识别到 ${tasks.length} 个独立截止时间,已拆分为多任务',
          needsUserConfirmation: true,
        );
      }
    }

    // 无法可靠拆分 — 返回单任务
    final single = _ruleExtract(rawNotice);
    return MultiExtractResult(
      tasks: [single],
      splitReason: '未识别到可独立拆分的多个任务,合并为单任务',
      needsUserConfirmation: false,
    );
  }

  /// 按日期边界拆分通知原文。
  List<String> _splitByDates(String raw, List<RegExpMatch> dateMatches) {
    if (dateMatches.length < 2) return [raw];
    // 简化策略:在连接词处拆分
    final connectors = RegExp(r'(并于|以及|然后|同时|另外|其次|接着|;|；)');
    final parts =
        raw.split(connectors).where((p) => p.trim().isNotEmpty).toList();
    if (parts.length >= 2) {
      return parts;
    }
    // 无连接词时,不拆分(避免错误拆分)
    return [raw];
  }

  @override
  Future<DuplicateCheckResult> checkDuplicate({
    required String content,
    String? sourceName,
    String? taskName,
    DateTime? deadline,
    required List<RecentNoticeItem> recentNotices,
  }) async {
    await Future.delayed(const Duration(milliseconds: 150));

    final contentHash = _hashContent(content);
    final matches = <DuplicateMatch>[];

    for (final recent in recentNotices) {
      final similarity = _computeSimilarity(content, recent);
      final reasons = <String>[];

      if (similarity >= 0.85) {
        reasons.add('content_similarity');
      }
      if (recent.sourceText != null &&
          _hashContent(recent.sourceText!) == contentHash) {
        reasons.add('content_hash');
      }
      if (sourceName != null &&
          sourceName.isNotEmpty &&
          sourceName == recent.sourceName &&
          deadline != null &&
          recent.deadline != null &&
          (deadline.difference(recent.deadline!).inMinutes.abs() <= 60)) {
        reasons.addAll(['source_name', 'deadline']);
      }
      if (taskName != null &&
          taskName.isNotEmpty &&
          taskName == recent.task &&
          deadline != null &&
          recent.deadline != null &&
          (deadline.difference(recent.deadline!).inMinutes.abs() <= 60)) {
        reasons.addAll(['task', 'deadline']);
      }

      if (reasons.isNotEmpty && similarity >= 0.7) {
        matches.add(
          DuplicateMatch(
            noticeId: recent.noticeId,
            title: recent.title ?? recent.task ?? '已存在通知',
            sourceName: recent.sourceName,
            deadline: recent.deadline,
            similarity: similarity,
            reasons: reasons,
          ),
        );
      }
    }

    matches.sort((a, b) => b.similarity.compareTo(a.similarity));

    return DuplicateCheckResult(
      isDuplicate: matches.isNotEmpty,
      matches: matches,
      contentHash: contentHash,
      note: '仅提示可能重复,不会自动覆盖原待办。请人工确认后决定是否继续保存。',
    );
  }

  /// 计算内容哈希(模拟 SHA256,非密码学安全)。
  String _hashContent(String text) {
    final normalized = text.replaceAll(RegExp(r'\s+'), '');
    var hash = 0x811C9DC5;
    for (final c in normalized.codeUnits) {
      hash = (hash ^ c) * 0x01000193 & 0xFFFFFFFF;
    }
    return 'mock_${hash.toRadixString(16).padLeft(8, '0')}';
  }

  /// 计算字符级 Jaccard 相似度。
  double _computeSimilarity(String a, RecentNoticeItem b) {
    final textA =
        a.replaceAll(RegExp(r'[\s\p{P}]', unicode: true), '').toLowerCase();
    final textB = (b.sourceText ?? '')
        .replaceAll(RegExp(r'[\s\p{P}]', unicode: true), '')
        .toLowerCase();
    if (textA.isEmpty || textB.isEmpty) return 0.0;
    final setA = textA.runes.toSet();
    final setB = textB.runes.toSet();
    final intersection = setA.intersection(setB).length;
    final union = setA.union(setB).length;
    return union == 0 ? 0.0 : intersection / union;
  }
}

/// Mock 任务仓库 — 内存实现,可从持久化层恢复与重置。
class MockTaskRepository implements TaskRepository {
  MockTaskRepository({List<Task>? initial}) {
    _tasks.addAll(initial ?? MockData.tasks);
  }

  final List<Task> _tasks = [];
  final _controller = StreamController<List<Task>>.broadcast();

  /// 当前内存任务的可持久化快照(包括已删除项)。
  @override
  List<Task> get snapshot => List.unmodifiable(_tasks);

  @override
  List<Task> get tasks => List.unmodifiable(
        _tasks.where((t) => !t.deleted).toList()..sort(_byDeadlineThenPriority),
      );

  @override
  Stream<List<Task>> watchTasks() =>
      _controller.stream.map((list) => List.unmodifiable(list));

  void _emit() {
    _controller.add(tasks);
  }

  @override
  Future<Task> createTask(Task task) async {
    await Future.delayed(const Duration(milliseconds: 120));
    _tasks.add(task);
    _emit();
    return task;
  }

  @override
  Future<void> updateTask(Task task) async {
    await Future.delayed(const Duration(milliseconds: 100));
    final i = _tasks.indexWhere((t) => t.id == task.id);
    if (i >= 0) _tasks[i] = task;
    _emit();
  }

  @override
  Future<void> softDelete(String taskId) async {
    final i = _tasks.indexWhere((t) => t.id == taskId);
    if (i >= 0) _tasks[i] = _tasks[i].copyWith(deleted: true);
    _emit();
  }

  @override
  Future<void> restore(String taskId) async {
    final i = _tasks.indexWhere((t) => t.id == taskId);
    if (i >= 0) _tasks[i] = _tasks[i].copyWith(deleted: false);
    _emit();
  }

  @override
  Future<void> hardDelete(String taskId) async {
    _tasks.removeWhere((t) => t.id == taskId);
    _emit();
  }

  /// 清空所有任务(用于"清除本地数据")。
  @override
  Future<void> clearAll() async {
    _tasks.clear();
    _emit();
  }

  /// 重置为 MockData 演示数据(用于"恢复演示数据")。
  @override
  Future<void> resetToDemo() async {
    _tasks
      ..clear()
      ..addAll(MockData.tasks);
    _emit();
  }

  /// 从持久化数据恢复(替换内存数据)。
  @override
  Future<void> restoreFrom(List<Task> saved) async {
    _tasks
      ..clear()
      ..addAll(saved);
    _emit();
  }

  @override
  Future<List<Task>> getByCategory(TaskCategory category) async =>
      tasks.where((t) => t.category == category).toList();

  @override
  Future<List<Task>> getUpcoming({int limit = 5}) async =>
      tasks.where((t) => !t.completed && t.deadline != null).toList()
        ..sort((a, b) => a.deadline!.compareTo(b.deadline!));

  @override
  Future<List<Task>> getCompleted() async =>
      tasks.where((t) => t.completed).toList();

  @override
  Future<List<Task>> getToday() async {
    final now = DateTime.now();
    return tasks.where((t) {
      if (t.completed) return false;
      if (t.deadline == null) return false;
      final d = t.deadline!;
      return d.year == now.year && d.month == now.month && d.day == now.day;
    }).toList();
  }

  int _byDeadlineThenPriority(Task a, Task b) {
    if (a.completed != b.completed) return a.completed ? 1 : -1;
    final ad = a.deadline;
    final bd = b.deadline;
    if (ad != null && bd != null) return ad.compareTo(bd);
    if (ad != null) return -1;
    if (bd != null) return 1;
    return b.priority.weight.compareTo(a.priority.weight);
  }

  void dispose() => _controller.close();
}

/// Mock AI 导员聊天服务 — 模拟流式输出 + 模拟知识库引用。
///
/// 重要:所有回答基于模拟知识库,明确标注"模拟资料来源",
/// 不伪造真实学校政策。
class MockCounselorChatService implements CounselorChatService {
  MockCounselorChatService({required this.knowledgeBase});

  final KnowledgeBaseService knowledgeBase;
  bool _stopRequested = false;

  @override
  Future<String> send(
    String message, {
    required String conversationId,
    CounselorContext context = const CounselorContext(),
    void Function(String chunk)? onChunk,
    void Function(List<KnowledgeSource> sources)? onSources,
    void Function(List<SuggestedAction> actions)? onActions,
    void Function(ChatFinalMeta meta)? onFinalMeta,
    void Function()? onTyping,
  }) async {
    _stopRequested = false;
    onTyping?.call();
    await Future.delayed(const Duration(milliseconds: 420));

    final sources = await knowledgeBase.search(message, limit: 2);
    onSources?.call(sources);
    await Future.delayed(const Duration(milliseconds: 220));

    final reply = _buildReply(message, sources, context);
    final actions = _buildActions(message);

    // 逐字流式输出(按 UTF-16 码单元拆分,中文 BMP 字符可正常逐字显示)
    final chars = reply.split('');
    final buffer = StringBuffer();
    for (final ch in chars) {
      if (_stopRequested) break;
      buffer.write(ch);
      onChunk?.call(ch);
      await Future.delayed(const Duration(milliseconds: 22));
    }

    onActions?.call(actions);
    // Mock 模式:固定推导为 mockDemo + medium 证据等级
    // 同时回填上下文使用情况(对齐要求 #11,Mock 也返回 contextUsed/Warnings)
    final contextUsed = <String, dynamic>{};
    if (context.courseId != null) contextUsed['course_id'] = context.courseId;
    if (context.classId != null) contextUsed['class_id'] = context.classId;
    if (context.assignmentId != null) {
      contextUsed['assignment_id'] = context.assignmentId;
    }
    if (context.announcementId != null) {
      contextUsed['announcement_id'] = context.announcementId;
    }
    if (context.recentTasks.isNotEmpty) {
      contextUsed['recent_tasks_count'] = context.recentTasks.length;
      contextUsed['recent_tasks_verified_count'] = 0;
    }
    final contextWarnings = <String>[];
    if (context.expressionSignal != null) {
      contextWarnings.add('Mock 模式:expression_signal 未接入,已忽略');
    }
    onFinalMeta?.call(
      ChatFinalMeta(
        mode: sources.isEmpty ? 'no_knowledge' : 'retrieval_summary',
        evidenceLevel: sources.isEmpty ? 'none' : 'medium',
        confidence: sources.isEmpty ? 0.0 : 0.6,
        warnings: sources.isEmpty ? ['Mock 模式:无可靠资料'] : const [],
        needsHumanConfirmation: false,
        hasUserDocs: false,
        hasDemoDocs: sources.isNotEmpty,
        contextUsed: contextUsed,
        contextWarnings: contextWarnings,
      ),
    );
    return buffer.toString();
  }

  @override
  Future<String?> generateProactiveReminder(List<Task> tasks) async {
    final upcoming = tasks
        .where((t) => !t.completed && t.deadline != null)
        .toList()
      ..sort((a, b) => a.deadline!.compareTo(b.deadline!));
    if (upcoming.isEmpty) return null;
    final soon = upcoming.first;
    final remaining = soon.deadline!.difference(DateTime.now());
    if (remaining.inHours < 24) {
      return '提醒你一下,「${soon.title}」临近截止,大约还剩 '
          '${remaining.inHours} 小时,材料准备得怎么样了?需要我帮你梳理一下吗?';
    }
    return '今天有 ${upcoming.length} 项待办,最紧急的是「${soon.title}」,'
        '可以优先处理它。';
  }

  @override
  void stop() => _stopRequested = true;

  String _buildReply(
    String message,
    List<KnowledgeSource> sources,
    CounselorContext context,
  ) {
    final msg = message.trim();
    // 上下文条幅前缀(若从课程/任务/通知进入,Mock 也体现上下文)
    final ctxPrefix = context.contextLabel != null
        ? '(上下文:${context.contextLabel})\n\n'
        : '';
    if (msg.contains('综合测评')) {
      return '$ctxPrefix综合测评由学业成绩、思想品德、社会实践、创新创业四部分组成,'
          '各占 60%、15%、15%、10%。你需要准备:① 本学期成绩单;'
          '② 思想品德评议表;③ 社会实践证明(志愿服务、社团活动等);'
          '④ 创新创业材料(竞赛、论文、专利等,可选项)。\n\n'
          '材料由班长汇总后交辅导员。下方引用了模拟资料来源,仅供参考,'
          '具体以学校最新文件为准。';
    }
    if (msg.contains('实践') && (msg.contains('申请') || msg.contains('学分'))) {
      return '$ctxPrefix实践学分申请流程:① 填写实践申请表;② 准备活动证明与总结报告;'
          '③ 纸质版交学院办公室,电子版发指定邮箱;④ 学院审核认定。\n\n'
          '注意实践学分需在毕业前完成认定,逾期不予受理。'
          '我可以帮你把这条通知整理成待办,设置提醒。';
    }
    if (msg.contains('奖学金')) {
      return '$ctxPrefix校级奖学金要求:一等奖学金综合测评排名前 5% 且无挂科;'
          '二等奖学金排名前 15%。申请需在学生系统提交,附个人陈述和成绩单,\n'
          '结果公示 3 个工作日。\n\n'
          '下面是模拟资料来源,正式申请前请确认学院当年的具体细则。';
    }
    if (msg.contains('快截止') || msg.contains('任务')) {
      // 若上下文带有真实 recent_tasks,Mock 也基于真实任务回复
      if (context.recentTasks.isNotEmpty) {
        final titles = context.recentTasks
            .take(3)
            .map((t) => '「${t.title}」')
            .join('、');
        return '$ctxPrefix你最近有这些待办:$titles。\n\n'
            '建议先处理截止最近的一项,需要我帮你拆分今天的任务,'
            '或者开启学习陪伴专注一段时间吗?';
      }
      return '$ctxPrefix我帮你看了下,你有 2 项任务临近截止:「综合测评材料汇总」'
          '和「提交实践申请表」。建议今天先处理综合测评,因为它的截止更近。\n\n'
          '需要我帮你拆分今天的任务,或者开启学习陪伴专注一段时间吗?';
    }
    if (msg.contains('拆分') || msg.contains('安排')) {
      return '$ctxPrefix好的,我帮你拆分一下今天:\n'
          '① 上午:整理综合测评的学业成绩与思想品德材料(约 40 分钟);\n'
          '② 下午:补齐社会实践证明(约 30 分钟);\n'
          '③ 晚上:写实践申请表的总结报告(约 50 分钟)。\n\n'
          '每段之间安排 10 分钟休息,效率会更好。要不要现在开启学习陪伴?';
    }
    if (msg.contains('选课')) {
      return '$ctxPrefix通识选修课补退选在每学期第 8 周,通过教务系统操作,'
          '每门课容量有限先到先得。退选不影响其他已选课程。'
          '具体操作路径:教务系统 → 选课管理 → 补退选。';
    }
    return '$ctxPrefix我理解你想了解「$msg」。当前我使用的是模拟知识库,'
        '能回答综合测评、实践学分、奖学金、选课等常见问题。\n\n'
        '如果是更具体的个人情况,建议你咨询辅导员或学院办公室,'
        '他们能给你最准确的信息。';
  }

  List<SuggestedAction> _buildActions(String message) {
    if (message.contains('实践') || message.contains('通知')) {
      return const [
        SuggestedAction(
          id: 'a_extract',
          label: '去整理通知',
          type: SuggestedActionType.navigate,
          payload: '/notifications/extract',
        ),
      ];
    }
    if (message.contains('任务') || message.contains('拆分')) {
      return const [
        SuggestedAction(
          id: 'a_study',
          label: '开启学习陪伴',
          type: SuggestedActionType.navigate,
          payload: '/study',
        ),
        SuggestedAction(
          id: 'a_tasks',
          label: '查看待办',
          type: SuggestedActionType.navigate,
          payload: '/tasks',
        ),
      ];
    }
    return const [];
  }
}

/// Mock 知识库服务 — 关键词匹配模拟资料。
class MockKnowledgeBaseService implements KnowledgeBaseService {
  @override
  Future<List<KnowledgeSource>> get sources async => MockData.knowledgeSources;

  @override
  Future<List<KnowledgeSource>> search(String query, {int limit = 3}) async {
    await Future.delayed(const Duration(milliseconds: 180));
    final q = query.toLowerCase();
    final scored = MockData.knowledgeSources.map((s) {
      var score = 0.0;
      final text = '${s.title} ${s.snippet ?? ''}'.toLowerCase();
      if (q.contains('综合测评') && text.contains('综合测评')) score += 0.5;
      if (q.contains('实践') && text.contains('实践')) score += 0.5;
      if (q.contains('奖学金') && text.contains('奖学金')) score += 0.5;
      if (q.contains('选课') && text.contains('选课')) score += 0.5;
      score += s.relevance * 0.3;
      return MapEntry(s, score);
    }).toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    return scored
        .where((e) => e.value > 0.3)
        .take(limit)
        .map((e) => e.key)
        .toList();
  }
}

/// Mock 学习会话仓库 — 内存状态机,对齐后端 API 行为。
///
/// 实现完整状态机: active --pause--> paused --resume--> active --finish--> completed。
/// 同时维护休息记录(StudyBreak)与累计暂停秒数。
///
/// 与后端 [ApiStudySessionRepository] 实现同一接口,可在 AppConfig 切换时无缝替换。
class MockStudySessionRepository implements StudySessionRepository {
  StudySession? _current;
  final _controller = StreamController<StudySession>.broadcast();
  final List<StudySession> _history = [];
  DateTime? _startedAt;
  int _elapsedSeconds = 0;
  int _pauseSeconds = 0;
  Timer? _tick;
  final List<StudyBreak> _breaks = [];

  MockStudySessionRepository() {
    _history.addAll(MockData.studyHistory);
  }

  /// 注入一个预设的"未结束会话",用于测试应用重启后恢复场景。
  ///
  /// 模拟应用重启后从后端拉取到的未结束会话:
  /// - 更新 [_current] 并通过流发射,使 [currentStudySessionProvider] 收到更新
  /// - 同步内部计时器状态,使后续 pause/resume/finish 行为正确
  ///
  /// **注意**:此方法不启动 Mock 的秒级 tick — 真实后端模式下 duration 由后端
  /// 在 pause/finish 时计算并返回,不需要客户端 tick。测试场景下启动 tick 会
  /// 留下 pending FakeTimer 导致测试断言失败。
  ///
  /// **仅供测试使用**(对应 [ApiStudySessionRepository.getActiveSession]
  /// 在拉取到未结束会话后调用 `_emit(session)` 的行为)。
  void injectForRecovery(StudySession session) {
    _current = session;
    _startedAt = session.startedAt;
    _elapsedSeconds = session.durationSeconds;
    _pauseSeconds = session.pauseSeconds;
    _breaks
      ..clear()
      ..addAll(session.breaks);
    // 不启动 tick — 见方法文档说明
    _stopTick();
    _emit();
  }

  @override
  StudySession? get current => _current;

  @override
  Stream<StudySession> watchCurrent() => _controller.stream;

  @override
  Future<StudySession> start({
    String? goal,
    String? relatedTaskId,
  }) async {
    await Future.delayed(const Duration(milliseconds: 80));
    _startedAt = DateTime.now();
    _elapsedSeconds = 0;
    _pauseSeconds = 0;
    _breaks.clear();
    _current = StudySession(
      id: 's_${DateTime.now().millisecondsSinceEpoch}',
      startedAt: _startedAt!,
      durationSeconds: 0,
      state: StudyState.focusing,
      goalId: goal,
      taskId: relatedTaskId,
      status: StudySessionStatus.active,
      breaks: const [],
    );
    _startTick();
    _emit();
    return _current!;
  }

  @override
  Future<StudySession> pause({String? reason}) async {
    if (_current == null) {
      throw const ApiException(
        code: 'NO_ACTIVE_SESSION',
        message: '当前没有进行中的学习会话',
      );
    }
    if (_current!.status != StudySessionStatus.active) {
      throw const ApiException(
        code: 'INVALID_TRANSITION',
        message: '当前状态不允许暂停,仅 active 会话可暂停',
      );
    }
    await Future.delayed(const Duration(milliseconds: 60));
    _stopTick();
    final now = DateTime.now();
    _breaks.add(
      StudyBreak(
        id: 'brk_${now.millisecondsSinceEpoch}',
        sessionId: _current!.id,
        startedAt: now,
        reason: reason,
        createdAt: now,
      ),
    );
    _current = _current!.copyWith(
      state: StudyState.paused,
      durationSeconds: _elapsedSeconds,
      status: StudySessionStatus.paused,
      pausedAt: now,
      breaks: List.unmodifiable(_breaks),
    );
    _emit();
    return _current!;
  }

  @override
  Future<StudySession> resume() async {
    if (_current == null) {
      throw const ApiException(
        code: 'NO_ACTIVE_SESSION',
        message: '当前没有进行中的学习会话',
      );
    }
    if (_current!.status != StudySessionStatus.paused) {
      throw const ApiException(
        code: 'INVALID_TRANSITION',
        message: '当前状态不允许恢复,仅 paused 会话可恢复',
      );
    }
    await Future.delayed(const Duration(milliseconds: 60));
    final now = DateTime.now();
    // 关闭最近一条未结束的休息记录,累加 pause_seconds
    final openIdx = _breaks.lastIndexWhere((b) => b.isOpen);
    if (openIdx >= 0) {
      final openBreak = _breaks[openIdx];
      final addedPause = now.difference(openBreak.startedAt).inSeconds;
      if (addedPause > 0) _pauseSeconds += addedPause;
      _breaks[openIdx] = openBreak.copyWith(endedAt: now);
    }
    _current = _current!.copyWith(
      state: StudyState.focusing,
      status: StudySessionStatus.active,
      pausedAt: null,
      pauseSeconds: _pauseSeconds,
      breaks: List.unmodifiable(_breaks),
    );
    _startTick();
    _emit();
    return _current!;
  }

  @override
  Future<StudySession> finish({
    String? selfReport,
    List<String>? selfReportTags,
  }) async {
    if (_current == null) {
      throw const ApiException(
        code: 'NO_ACTIVE_SESSION',
        message: '当前没有进行中的学习会话',
      );
    }
    if (_current!.status == StudySessionStatus.completed) {
      throw const ApiException(
        code: 'INVALID_TRANSITION',
        message: '会话已结束,不能再次结束',
      );
    }
    await Future.delayed(const Duration(milliseconds: 80));
    _stopTick();
    final now = DateTime.now();
    // 关闭所有未结束的休息记录,累加 pause_seconds
    for (var i = 0; i < _breaks.length; i++) {
      if (_breaks[i].isOpen) {
        final addedPause = now.difference(_breaks[i].startedAt).inSeconds;
        if (addedPause > 0) _pauseSeconds += addedPause;
        _breaks[i] = _breaks[i].copyWith(endedAt: now);
      }
    }
    final ended = _current!.copyWith(
      endedAt: now,
      durationSeconds: _elapsedSeconds,
      state: StudyState.completed,
      status: StudySessionStatus.completed,
      pausedAt: null,
      pauseSeconds: _pauseSeconds,
      selfReport: selfReport,
      selfReportMood: selfReport,
      selfReportTags: selfReportTags ?? const [],
      breaks: List.unmodifiable(_breaks),
    );
    _history.insert(0, ended);
    _current = null;
    _startedAt = null;
    _elapsedSeconds = 0;
    _pauseSeconds = 0;
    _breaks.clear();
    return ended;
  }

  @override
  Future<StudySession> updateSession({
    String? goal,
    String? relatedTaskId,
    String? selfReport,
    List<String>? selfReportTags,
    Map<String, dynamic>? expressionSignal,
  }) async {
    if (_current == null) {
      throw const ApiException(
        code: 'NO_ACTIVE_SESSION',
        message: '当前没有进行中的学习会话',
      );
    }
    await Future.delayed(const Duration(milliseconds: 50));
    _current = _current!.copyWith(
      goalId: goal ?? _current!.goalId,
      taskId: relatedTaskId ?? _current!.taskId,
      selfReport: selfReport ?? _current!.selfReport,
      selfReportMood: selfReport ?? _current!.selfReportMood,
      selfReportTags: selfReportTags ?? _current!.selfReportTags,
      expressionSignal: expressionSignal ?? _current!.expressionSignal,
    );
    _emit();
    return _current!;
  }

  @override
  Future<StudySession?> getActiveSession() async {
    await Future.delayed(const Duration(milliseconds: 50));
    return _current;
  }

  @override
  Future<StudySession?> getSession(String sessionId) async {
    await Future.delayed(const Duration(milliseconds: 40));
    if (_current?.id == sessionId) return _current;
    for (final s in _history) {
      if (s.id == sessionId) return s;
    }
    return null;
  }

  @override
  Future<List<StudySession>> history({int limit = 30}) async =>
      _history.take(limit).toList();

  @override
  Future<Duration> todayTotal() async {
    final now = DateTime.now();
    var total = 0;
    for (final s in _history) {
      if (s.startedAt.year == now.year &&
          s.startedAt.month == now.month &&
          s.startedAt.day == now.day) {
        total += s.durationSeconds;
      }
    }
    return Duration(seconds: total);
  }

  void _startTick() {
    _stopTick();
    _tick = Timer.periodic(const Duration(seconds: 1), (_) {
      _elapsedSeconds++;
      if (_current != null) {
        _current = _current!.copyWith(durationSeconds: _elapsedSeconds);
        _emit();
      }
    });
  }

  void _stopTick() {
    _tick?.cancel();
    _tick = null;
  }

  void _emit() {
    if (_current != null) _controller.add(_current!);
  }

  /// 历史快照(可持久化)。
  @override
  List<StudySession> get historySnapshot => List.unmodifiable(_history);

  /// 从持久化历史恢复(替换内存历史)。
  @override
  Future<void> restoreHistoryFrom(List<StudySession> saved) async {
    _history
      ..clear()
      ..addAll(saved);
    _emit();
  }

  /// 清除全部历史(用于"清除本地数据")。
  @override
  Future<void> clearHistory() async {
    _history.clear();
    _emit();
  }

  /// 重置为 MockData 演示数据(用于"恢复演示数据")。
  @override
  Future<void> resetToDemo() async {
    _history
      ..clear()
      ..addAll(MockData.studyHistory);
    _emit();
  }

  void dispose() {
    _stopTick();
    _controller.close();
  }
}

/// Mock 表情识别服务 — 模拟 CNN 输出 + 多帧平滑。
///
/// 明确标注 Mock 模式,不伪造真实 CNN 能力。
/// 可通过 [injectMockLabel] 注入指定表情用于演示。
///
/// **仅在 Debug 模式且 USE_MOCK_EXPRESSION=true 时启用**(AGENTS.md §2.4)。
/// Release 构建下 `AppConfig.useMockExpressionRecognition` 始终为 false,
/// 此类不会被实例化,UI 也不会显示 Mock 标识。
class MockExpressionRecognitionService implements ExpressionRecognitionService {
  MockExpressionRecognitionService({
    required double confidenceThreshold,
    required int stableFrames,
    required this.suggestionCooldownMinutes,
  }) : _smoother = ExpressionSmoother(
          confidenceThreshold: confidenceThreshold,
          stableFrames: stableFrames,
        );

  final ExpressionSmoother _smoother;
  final int suggestionCooldownMinutes;
  final _controller = StreamController<ExpressionResult>.broadcast();
  final _statusController =
      StreamController<ExpressionServiceStatus>.broadcast()..add(
    const ExpressionServiceStatus(
      modelState: ExpressionModelState.ready,
      cameraState: CameraState.idle,
      modelVersion: 'mock-v0.1',
    ),
  );
  Timer? _timer;
  bool _running = false;
  final _rand = Random();

  /// 当前注入的 Mock 标签(用于演示模式手动控制)。
  ExpressionLabel? _injectedLabel;

  @override
  Stream<ExpressionResult> get results => _controller.stream;

  @override
  Stream<ExpressionServiceStatus> get status => _statusController.stream;

  @override
  bool get isRunning => _running;

  /// 注入 Mock 表情(演示用)。null 表示随机漂移。
  void injectMockLabel(ExpressionLabel? label) => _injectedLabel = label;

  @override
  Future<void> initialize() async {
    await Future.delayed(const Duration(milliseconds: 200));
    _statusController.add(
      const ExpressionServiceStatus(
        modelState: ExpressionModelState.ready,
        cameraState: CameraState.idle,
        modelVersion: 'mock-v0.1',
      ),
    );
  }

  @override
  Future<void> start() async {
    if (_running) return;
    _running = true;
    _smoother.reset();
    _statusController.add(
      const ExpressionServiceStatus(
        modelState: ExpressionModelState.ready,
        cameraState: CameraState.running,
        modelVersion: 'mock-v0.1',
      ),
    );
    _timer = Timer.periodic(const Duration(milliseconds: 500), (_) {
      _produceFrame();
    });
  }

  @override
  Future<void> pause() async {
    _timer?.cancel();
    _timer = null;
    _running = false;
    _statusController.add(
      const ExpressionServiceStatus(
        modelState: ExpressionModelState.ready,
        cameraState: CameraState.stopped,
        modelVersion: 'mock-v0.1',
      ),
    );
  }

  @override
  Future<void> stop() async {
    await pause();
    _smoother.reset();
  }

  @override
  Future<void> dispose() async {
    await stop();
    await _controller.close();
    await _statusController.close();
  }

  void _produceFrame() {
    final probabilities = _generateProbabilities(_injectedLabel);
    final result = _smoother.smooth(
      probabilities,
      DateTime.now(),
      modelVersion: 'mock-v0.1',
    );
    _controller.add(result);
  }

  Map<ExpressionLabel, double> _generateProbabilities(
    ExpressionLabel? forced,
  ) {
    final labels =
        ExpressionLabel.values.where((l) => l != ExpressionLabel.noFace);
    final probs = <ExpressionLabel, double>{};
    if (forced != null && forced != ExpressionLabel.noFace) {
      // 围绕 forced 生成,加入少量噪声
      final center = 0.55 + _rand.nextDouble() * 0.25;
      probs[forced] = center;
      var remaining = 1 - center;
      final others = labels.where((l) => l != forced).toList()..shuffle();
      for (var i = 0; i < others.length; i++) {
        final v = i == others.length - 1
            ? remaining
            : remaining * (0.2 + _rand.nextDouble() * 0.3);
        probs[others[i]] = v;
        remaining -= v;
      }
      probs[ExpressionLabel.noFace] = 0;
      return probs;
    }
    // 随机漂移:以 neutral 为中心,偶尔偏向其他
    final r = _rand.nextDouble();
    ExpressionLabel main;
    if (r < 0.5) {
      main = ExpressionLabel.neutral;
    } else if (r < 0.7) {
      main = ExpressionLabel.happy;
    } else if (r < 0.8) {
      main = ExpressionLabel.sad;
    } else if (r < 0.9) {
      main = ExpressionLabel.surprise;
    } else {
      main = ExpressionLabel.unknown;
    }
    final center = 0.4 + _rand.nextDouble() * 0.25;
    probs[main] = center;
    var remaining = 1 - center;
    final others = labels.where((l) => l != main).toList()..shuffle();
    for (var i = 0; i < others.length; i++) {
      final v = i == others.length - 1
          ? remaining
          : remaining * (0.15 + _rand.nextDouble() * 0.25);
      probs[others[i]] = v;
      remaining -= v;
    }
    probs[ExpressionLabel.noFace] = 0;
    return probs;
  }
}

/// Mock 权限服务。
class MockPermissionService implements PermissionService {
  bool _camera = false;
  bool _notifications = true;

  /// 测试用:模拟永久拒绝(用于验证 UI 不会反复弹窗)。
  bool _cameraPermanentlyDenied = false;

  /// 测试用:设置摄像头永久拒绝状态。
  void setCameraPermanentlyDenied(bool value) {
    _cameraPermanentlyDenied = value;
    _camera = false;
  }

  @override
  Future<bool> requestCamera() async {
    await Future.delayed(const Duration(milliseconds: 300));
    if (_cameraPermanentlyDenied) return false;
    _camera = true;
    return _camera;
  }

  @override
  Future<bool> requestNotifications() async {
    await Future.delayed(const Duration(milliseconds: 200));
    _notifications = true;
    return _notifications;
  }

  @override
  Future<bool> get hasCamera async => _camera;

  @override
  Future<bool> get hasNotifications async => _notifications;

  @override
  Future<PermissionStatus> get cameraPermissionStatus async {
    if (_cameraPermanentlyDenied) return PermissionStatus.permanentlyDenied;
    return _camera
        ? PermissionStatus.granted
        : PermissionStatus.notDetermined;
  }

  @override
  Future<PermissionStatus> get notificationPermissionStatus async =>
      _notifications
          ? PermissionStatus.granted
          : PermissionStatus.notDetermined;

  @override
  Future<void> openAppSettings() async {
    // Mock: no-op
  }
}

/// Mock 分析服务。
class MockAnalyticsService implements AnalyticsService {
  @override
  Future<void> logEvent(String name, {Map<String, dynamic>? params}) async {}

  @override
  Future<void> setUserId(String? userId) async {}
}
