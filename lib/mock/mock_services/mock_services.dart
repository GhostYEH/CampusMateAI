import 'dart:async';
import 'dart:math';

import '../../data/models/models.dart';
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
    void Function(String chunk)? onChunk,
    void Function(List<KnowledgeSource> sources)? onSources,
    void Function(List<SuggestedAction> actions)? onActions,
    void Function()? onTyping,
  }) async {
    _stopRequested = false;
    onTyping?.call();
    await Future.delayed(const Duration(milliseconds: 420));

    final sources = await knowledgeBase.search(message, limit: 2);
    onSources?.call(sources);
    await Future.delayed(const Duration(milliseconds: 220));

    final reply = _buildReply(message, sources);
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

  String _buildReply(String message, List<KnowledgeSource> sources) {
    final msg = message.trim();
    if (msg.contains('综合测评')) {
      return '综合测评由学业成绩、思想品德、社会实践、创新创业四部分组成,'
          '各占 60%、15%、15%、10%。你需要准备:① 本学期成绩单;'
          '② 思想品德评议表;③ 社会实践证明(志愿服务、社团活动等);'
          '④ 创新创业材料(竞赛、论文、专利等,可选项)。\n\n'
          '材料由班长汇总后交辅导员。下方引用了模拟资料来源,仅供参考,'
          '具体以学校最新文件为准。';
    }
    if (msg.contains('实践') && (msg.contains('申请') || msg.contains('学分'))) {
      return '实践学分申请流程:① 填写实践申请表;② 准备活动证明与总结报告;'
          '③ 纸质版交学院办公室,电子版发指定邮箱;④ 学院审核认定。\n\n'
          '注意实践学分需在毕业前完成认定,逾期不予受理。'
          '我可以帮你把这条通知整理成待办,设置提醒。';
    }
    if (msg.contains('奖学金')) {
      return '校级奖学金要求:一等奖学金综合测评排名前 5% 且无挂科;'
          '二等奖学金排名前 15%。申请需在学生系统提交,附个人陈述和成绩单,\n'
          '结果公示 3 个工作日。\n\n'
          '下面是模拟资料来源,正式申请前请确认学院当年的具体细则。';
    }
    if (msg.contains('快截止') || msg.contains('任务')) {
      return '我帮你看了下,你有 2 项任务临近截止:「综合测评材料汇总」'
          '和「提交实践申请表」。建议今天先处理综合测评,因为它的截止更近。\n\n'
          '需要我帮你拆分今天的任务,或者开启学习陪伴专注一段时间吗?';
    }
    if (msg.contains('拆分') || msg.contains('安排')) {
      return '好的,我帮你拆分一下今天:\n'
          '① 上午:整理综合测评的学业成绩与思想品德材料(约 40 分钟);\n'
          '② 下午:补齐社会实践证明(约 30 分钟);\n'
          '③ 晚上:写实践申请表的总结报告(约 50 分钟)。\n\n'
          '每段之间安排 10 分钟休息,效率会更好。要不要现在开启学习陪伴?';
    }
    if (msg.contains('选课')) {
      return '通识选修课补退选在每学期第 8 周,通过教务系统操作,'
          '每门课容量有限先到先得。退选不影响其他已选课程。'
          '具体操作路径:教务系统 → 选课管理 → 补退选。';
    }
    return '我理解你想了解「$msg」。当前我使用的是模拟知识库,'
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

/// Mock 学习会话仓库。
class MockStudySessionRepository implements StudySessionRepository {
  StudySession? _current;
  final _controller = StreamController<StudySession>.broadcast();
  final List<StudySession> _history = [];
  DateTime? _startedAt;
  int _elapsedSeconds = 0;
  Timer? _tick;

  MockStudySessionRepository() {
    _history.addAll(MockData.studyHistory);
  }

  @override
  StudySession? get current => _current;

  @override
  Stream<StudySession> watchCurrent() => _controller.stream;

  @override
  Future<StudySession> start({String? goalId, String? taskId}) async {
    _startedAt = DateTime.now();
    _elapsedSeconds = 0;
    _current = StudySession(
      id: 's_${DateTime.now().millisecondsSinceEpoch}',
      startedAt: _startedAt!,
      durationSeconds: 0,
      state: StudyState.focusing,
      goalId: goalId,
      taskId: taskId,
    );
    _startTick();
    _emit();
    return _current!;
  }

  @override
  Future<void> pause() async {
    if (_current == null) return;
    _stopTick();
    _current = _current!.copyWith(
      state: StudyState.paused,
      durationSeconds: _elapsedSeconds,
    );
    _emit();
  }

  @override
  Future<void> resume() async {
    if (_current == null) return;
    _current = _current!.copyWith(state: StudyState.focusing);
    _startTick();
    _emit();
  }

  @override
  Future<StudySession> end({String? selfReportMood}) async {
    _stopTick();
    final ended = (_current ??
            StudySession(
              id: 's_empty',
              startedAt: DateTime.now(),
              durationSeconds: 0,
              state: StudyState.completed,
            ))
        .copyWith(
      endedAt: DateTime.now(),
      durationSeconds: _elapsedSeconds,
      state: StudyState.completed,
      selfReportMood: selfReportMood,
    );
    _history.insert(0, ended);
    _current = null;
    _startedAt = null;
    _elapsedSeconds = 0;
    _emit();
    return ended;
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
  Timer? _timer;
  bool _running = false;
  final _rand = Random();

  /// 当前注入的 Mock 标签(用于演示模式手动控制)。
  ExpressionLabel? _injectedLabel;

  @override
  Stream<ExpressionResult> get results => _controller.stream;

  @override
  bool get isRunning => _running;

  /// 注入 Mock 表情(演示用)。null 表示随机漂移。
  void injectMockLabel(ExpressionLabel? label) => _injectedLabel = label;

  @override
  Future<void> initialize() async {
    await Future.delayed(const Duration(milliseconds: 200));
  }

  @override
  Future<void> start() async {
    if (_running) return;
    _running = true;
    _smoother.reset();
    _timer = Timer.periodic(const Duration(milliseconds: 500), (_) {
      _produceFrame();
    });
  }

  @override
  Future<void> pause() async {
    _timer?.cancel();
    _timer = null;
    _running = false;
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

  @override
  Future<bool> requestCamera() async {
    await Future.delayed(const Duration(milliseconds: 300));
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
}

/// Mock 分析服务。
class MockAnalyticsService implements AnalyticsService {
  @override
  Future<void> logEvent(String name, {Map<String, dynamic>? params}) async {}

  @override
  Future<void> setUserId(String? userId) async {}
}
