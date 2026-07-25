import '../../data/models/models.dart';

/// Mock 数据 — 真实校园场景,无 Lorem Ipsum。
///
/// 时间字段相对 [DateTime.now()] 生成,保证演示时截止日期始终有意义。
class MockData {
  MockData._();

  static final _now = DateTime.now();

  /// 当前用户。
  static AppUser get currentUser => const AppUser(
        id: 'u_20240001',
        name: '林知夏',
        nickname: '知夏',
        studentId: '2024010132',
        college: '计算机与人工智能学院',
        grade: '2024级',
        avatarSeed: 'zhixia',
      );

  /// 校园通知列表(包含演示用的完整通知原文)。
  static List<CampusNotice> get notices => [
        CampusNotice(
          id: 'n_001',
          title: '关于2024级学生实践学分申请的通知',
          source: '教务处',
          publishedAt: _now.subtract(const Duration(hours: 5)),
          importance: NoticeImportance.important,
          content: '请2024级学生于10月20日前填写实践申请表,并将申请表和证明材料'
              '提交至学院办公室。实践学分需在毕业前完成认定,逾期不予受理。'
              '材料包括:实践申请表、活动证明、总结报告。'
              '提交方式:纸质版交至学院办公室(行政楼302),电子版发送至practice@school.edu.cn。',
          tags: const ['实践学分', '2024级'],
          read: false,
        ),
        CampusNotice(
          id: 'n_002',
          title: '2024-2025学年综合测评工作安排',
          source: '学生工作处',
          publishedAt: _now.subtract(const Duration(hours: 22)),
          importance: NoticeImportance.urgent,
          content: '各班级请于本周五前完成综合测评材料汇总。综合测评包括学业成绩、'
              '思想品德、社会实践、创新创业四部分。请同学们准备好相关证明材料,'
              '由班长统一收齐后交至辅导员处。详细评分细则见附件。',
          tags: const ['综合测评', '奖学金'],
          read: false,
        ),
        CampusNotice(
          id: 'n_003',
          title: '关于开展2025年校级奖学金评选的通知',
          source: '学生资助管理中心',
          publishedAt: _now.subtract(const Duration(days: 1, hours: 6)),
          importance: NoticeImportance.important,
          content: '校级一等奖学金要求综合测评排名前5%,且无挂科记录;二等奖学金排名前15%。'
              '申请同学请于11月5日前在学生系统提交申请,并附上个人陈述和成绩单。'
              '评选结果将在学院公示3个工作日。',
          tags: const ['奖学金', '评选'],
          read: true,
        ),
        CampusNotice(
          id: 'n_004',
          title: '第8周选课补退选安排',
          source: '教务处',
          publishedAt: _now.subtract(const Duration(days: 2)),
          importance: NoticeImportance.normal,
          content: '第8周通识选修课补退选时间为周一至周三。请同学们登录教务系统'
              '在"选课管理"中操作。每门课容量有限,先到先得。退选课程不影响'
              '已选其他课程。',
          tags: const ['选课', '通识'],
          read: true,
        ),
        CampusNotice(
          id: 'n_005',
          title: '校园心理健康周活动报名',
          source: '心理健康教育中心',
          publishedAt: _now.subtract(const Duration(days: 3)),
          importance: NoticeImportance.normal,
          content: '心理健康周将于下周一开幕,包含团体辅导、心理沙龙、减压工作坊等'
              '活动。感兴趣的同学请在公众号"心灵校园"报名,名额有限。'
              '参与活动可计入学时。',
          tags: const ['活动报名', '心理健康'],
          read: false,
        ),
      ];

  /// 待办任务(演示数据)。
  static List<Task> get tasks => [
        Task(
          id: 't_001',
          title: '提交实践申请表与证明材料',
          category: TaskCategory.practice,
          priority: TaskPriority.high,
          createdAt: _now.subtract(const Duration(days: 2)),
          source: TaskSource.noticeExtraction,
          sourceNoticeId: 'n_001',
          deadline: _now.add(const Duration(days: 3, hours: 6)),
          location: '行政楼302 学院办公室',
          materials: const [
            TaskMaterial(id: 'm_1', name: '实践申请表', required: true, done: true),
            TaskMaterial(id: 'm_2', name: '活动证明', required: true, done: false),
            TaskMaterial(id: 'm_3', name: '总结报告', required: true, done: false),
          ],
          reminderEnabled: true,
          reminderAt: _now.add(const Duration(days: 2)),
        ),
        Task(
          id: 't_002',
          title: '综合测评材料汇总',
          category: TaskCategory.comprehensiveEval,
          priority: TaskPriority.high,
          createdAt: _now.subtract(const Duration(days: 1)),
          source: TaskSource.noticeExtraction,
          sourceNoticeId: 'n_002',
          deadline: _now.add(const Duration(days: 1, hours: 4)),
          location: '辅导员办公室',
          description: '汇总学业成绩、思想品德、社会实践、创新创业四部分材料',
          materials: const [
            TaskMaterial(id: 'm_4', name: '成绩单', required: true, done: true),
            TaskMaterial(
              id: 'm_5',
              name: '社会实践证明',
              required: true,
              done: false,
            ),
            TaskMaterial(
              id: 'm_6',
              name: '创新创业材料',
              required: false,
              done: false,
            ),
          ],
          reminderEnabled: true,
          reminderAt: _now.add(const Duration(hours: 20)),
        ),
        Task(
          id: 't_003',
          title: '完成数据结构作业第四章',
          category: TaskCategory.study,
          priority: TaskPriority.medium,
          createdAt: _now.subtract(const Duration(hours: 10)),
          source: TaskSource.manual,
          deadline: _now.add(const Duration(days: 2)),
        ),
        Task(
          id: 't_004',
          title: '提交校级奖学金申请',
          category: TaskCategory.scholarship,
          priority: TaskPriority.high,
          createdAt: _now.subtract(const Duration(days: 3)),
          source: TaskSource.noticeExtraction,
          sourceNoticeId: 'n_003',
          deadline: _now.add(const Duration(days: 10)),
          description: '在学生系统提交申请,附个人陈述和成绩单',
          materials: const [
            TaskMaterial(id: 'm_7', name: '个人陈述', required: true, done: false),
            TaskMaterial(id: 'm_8', name: '成绩单', required: true, done: true),
          ],
        ),
        Task(
          id: 't_005',
          title: '补退选通识选修课',
          category: TaskCategory.courseSelection,
          priority: TaskPriority.medium,
          createdAt: _now.subtract(const Duration(days: 1)),
          source: TaskSource.noticeExtraction,
          sourceNoticeId: 'n_004',
          deadline: _now.add(const Duration(days: 4)),
          location: '教务系统',
        ),
        Task(
          id: 't_006',
          title: '复习高等数学期中考试',
          category: TaskCategory.study,
          priority: TaskPriority.high,
          createdAt: _now.subtract(const Duration(days: 5)),
          source: TaskSource.manual,
          deadline: _now.add(const Duration(days: 6)),
        ),
        // 已完成
        Task(
          id: 't_007',
          title: '提交英语阅读报告',
          category: TaskCategory.study,
          priority: TaskPriority.medium,
          createdAt: _now.subtract(const Duration(days: 4)),
          source: TaskSource.manual,
          completed: true,
          completedAt: _now.subtract(const Duration(hours: 8)),
          deadline: _now.subtract(const Duration(hours: 6)),
        ),
        Task(
          id: 't_008',
          title: '完成实验报告二',
          category: TaskCategory.study,
          priority: TaskPriority.medium,
          createdAt: _now.subtract(const Duration(days: 6)),
          source: TaskSource.manual,
          completed: true,
          completedAt: _now.subtract(const Duration(days: 1, hours: 5)),
        ),
      ];

  /// 知识库来源(模拟)。
  static List<KnowledgeSource> get knowledgeSources => [
        KnowledgeSource(
          id: 'k_001',
          title: '《大学生综合测评实施办法》',
          updatedAt: DateTime(_now.year - 1, 9, 1),
          source: '模拟资料来源',
          snippet: '综合测评由学业成绩、思想品德、社会实践、创新创业四部分组成,'
              '各占60%、15%、15%、10%。',
          relevance: 0.92,
        ),
        KnowledgeSource(
          id: 'k_002',
          title: '《实践学分认定与管理细则》',
          updatedAt: DateTime(_now.year - 1, 9, 10),
          source: '模拟资料来源',
          snippet: '实践学分需在毕业前完成认定,申请材料包括实践申请表、活动证明、总结报告。',
          relevance: 0.88,
        ),
        KnowledgeSource(
          id: 'k_003',
          title: '《校级奖学金评选办法》',
          updatedAt: DateTime(_now.year - 1, 9, 15),
          source: '模拟资料来源',
          snippet: '一等奖学金要求综合测评排名前5%且无挂科;二等奖学金排名前15%。',
          relevance: 0.85,
        ),
        KnowledgeSource(
          id: 'k_004',
          title: '《选课管理规定》',
          updatedAt: DateTime(_now.year - 1, 8, 20),
          source: '模拟资料来源',
          snippet: '通识选修课补退选在每学期第8周进行,通过教务系统操作。',
          relevance: 0.80,
        ),
      ];

  /// 快捷问题。
  static const List<String> quickQuestions = [
    '综合测评需要准备什么材料?',
    '实践学分怎样申请?',
    '奖学金申请有什么要求?',
    '我最近有哪些快截止的任务?',
    '帮我把今天的任务拆分一下。',
  ];

  /// 演示用的通知提取样例(可粘贴)。
  static const List<String> noticeSamples = [
    '请2024级学生于10月20日前填写实践申请表,并将申请表和证明材料'
        '提交至学院办公室。',
    '各班级请于本周五前完成综合测评材料汇总,材料包括学业成绩、思想品德、'
        '社会实践、创新创业四部分,由班长统一收齐后交至辅导员处。',
    '校级一等奖学金要求综合测评排名前5%,且无挂科记录。申请同学请于11月5日前'
        '在学生系统提交申请,并附上个人陈述和成绩单。',
  ];

  /// AI 导员初始问候。
  static String get counselorGreeting {
    final h = _now.hour;
    final String period;
    if (h >= 5 && h < 11) {
      period = '今天也要元气满满地开始';
    } else if (h >= 11 && h < 14) {
      period = '中午记得吃顿好的';
    } else if (h >= 14 && h < 18) {
      period = '下午继续加油';
    } else if (h >= 18 && h < 23) {
      period = '晚上学习别太晚';
    } else {
      period = '已经很晚了,注意休息';
    }
    return '知夏,$period。我整理了你今天的任务,有2项临近截止,需要我帮你安排一下吗?';
  }

  /// 学习会话历史(模拟)。
  static List<StudySession> get studyHistory => [
        StudySession(
          id: 's_001',
          startedAt: _now.subtract(const Duration(days: 1, hours: 3)),
          endedAt: _now.subtract(const Duration(days: 1, hours: 1)),
          durationSeconds: 5400,
          state: StudyState.completed,
          focusRatio: 0.82,
        ),
        StudySession(
          id: 's_002',
          startedAt: _now.subtract(const Duration(days: 2, hours: 5)),
          endedAt:
              _now.subtract(const Duration(days: 2, hours: 3, minutes: 30)),
          durationSeconds: 4500,
          state: StudyState.completed,
          focusRatio: 0.75,
        ),
        StudySession(
          id: 's_003',
          startedAt: _now.subtract(const Duration(days: 3, hours: 4)),
          endedAt:
              _now.subtract(const Duration(days: 3, hours: 2, minutes: 15)),
          durationSeconds: 6300,
          state: StudyState.completed,
          focusRatio: 0.68,
        ),
      ];

  /// 学习目标(可选)。
  static List<StudyGoal> get studyGoals => [
        const StudyGoal(id: 'g_001', title: '复习高数第三章', targetMinutes: 60),
        const StudyGoal(id: 'g_002', title: '完成数据结构实验', targetMinutes: 90),
      ];
}
