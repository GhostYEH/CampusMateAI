import '../../data/models/models.dart';

/// 多角色 Mock 数据 — 用于演示模式下的完整多角色数据链路。
///
/// 严格遵循 AGENTS.md §10 Mock 与演示模式:
/// - 3 门课程
/// - 4 个班级
/// - 30 名学生(分布在 4 个班级中)
/// - 教师发布的通知和任务
/// - 学生提交(已交 / 未交 / 逾期)
/// - 教师评分
///
/// 演示账号(密码统一为 Demo123456):
/// - student_demo  → 林知夏(已加入多个班级)
/// - teacher_demo  → 张明远(开课教师)
/// - admin_demo    → 系统管理员
class MultiRoleMockData {
  MultiRoleMockData._();

  /// 当前学期(用于所有课程统一)。
  static Semester get currentSemester {
    final now = DateTime.now();
    // 简化:9月-次年1月为上学期,2月-7月为下学期
    final isFall = now.month >= 9 || now.month <= 1;
    final year = now.month >= 9 ? now.year : now.year - 1;
    final nextYear = year + 1;
    final id = isFall ? '$year-$nextYear-1' : '$year-$nextYear-2';
    final name = isFall ? '$year-$nextYear 学年 第一学期' : '$year-$nextYear 学年 第二学期';
    return Semester(
      id: id,
      name: name,
      startDate: isFall ? DateTime(year, 9, 1) : DateTime(now.year, 2, 15),
      endDate: isFall ? DateTime(nextYear, 1, 25) : DateTime(now.year, 7, 10),
      isActive: true,
    );
  }

  // ===== 演示用户 =====

  /// 学生演示账号 — 林知夏(已加入多个班级)。
  static const AppUser studentDemoUser = AppUser(
    id: 'u_student_demo',
    name: '林知夏',
    nickname: '知夏',
    role: UserRole.student,
    avatarSeed: 'zhixia',
    studentId: '2024010132',
    college: '计算机与人工智能学院',
    major: '计算机科学与技术',
    grade: '2024级',
    className: '计科2024-1班',
  );

  /// 教师演示账号 — 张明远(开课教师)。
  static const AppUser teacherDemoUser = AppUser(
    id: 'u_teacher_demo',
    name: '张明远',
    nickname: '张老师',
    role: UserRole.teacher,
    avatarSeed: 'zhangmy',
    teacherId: 'T20180456',
    department: '计算机与人工智能学院',
    teacherTitle: '副教授',
  );

  /// 管理员演示账号。
  static const AppUser adminDemoUser = AppUser(
    id: 'u_admin_demo',
    name: '管理员',
    role: UserRole.admin,
    avatarSeed: 'admin',
    adminTitle: '系统管理员',
    scope: '全部',
  );

  /// 演示账号列表(用于登录页快捷登录)。
  static const List<DemoAccount> demoAccounts = [
    DemoAccount(
      username: 'student_demo',
      password: 'Demo123456',
      role: UserRole.student,
      displayName: '学生演示',
      subtitle: '林知夏 · 计算机科学与技术 2024级',
    ),
    DemoAccount(
      username: 'teacher_demo',
      password: 'Demo123456',
      role: UserRole.teacher,
      displayName: '教师演示',
      subtitle: '张明远 · 副教授',
    ),
    DemoAccount(
      username: 'admin_demo',
      password: 'Demo123456',
      role: UserRole.admin,
      displayName: '管理员演示',
      subtitle: '系统管理员',
    ),
  ];

  // ===== 教师与课程 =====

  /// 教师张明远的简要信息(用于嵌入 Course.teacher)。
  static const CourseTeacher teacherZhang = CourseTeacher(
    id: 'u_teacher_demo',
    name: '张明远',
    title: '副教授',
    department: '计算机与人工智能学院',
  );

  /// 第二位教师(开设计算机网络课程)。
  static const CourseTeacher teacherLiu = CourseTeacher(
    id: 'u_teacher_liu',
    name: '刘文静',
    title: '讲师',
    department: '计算机与人工智能学院',
  );

  /// 3 门课程。
  static List<Course> get courses {
    final sem = currentSemester;
    return [
      Course(
        id: 'c_hm001',
        code: 'CS101',
        name: '高等数学',
        semester: sem,
        teacher: teacherZhang,
        description: '微积分基础与应用,涵盖极限、导数、积分及其工程应用。',
        creditHours: 4,
        startDate: sem.startDate,
        endDate: sem.endDate,
        classIds: const ['cl_hm001_1', 'cl_hm001_2'],
        color: 0xFF2F6486,
        studentCount: 60,
        classCount: 2,
      ),
      Course(
        id: 'c_ds002',
        code: 'CS201',
        name: '数据结构',
        semester: sem,
        teacher: teacherZhang,
        description: '线性表、树、图、排序与查找算法,以 Java 实现为主。',
        creditHours: 3,
        startDate: sem.startDate,
        endDate: sem.endDate,
        classIds: const ['cl_ds002_1'],
        color: 0xFF4E8C6A,
        studentCount: 30,
        classCount: 1,
      ),
      Course(
        id: 'c_cn003',
        code: 'CS301',
        name: '计算机网络',
        semester: sem,
        teacher: teacherLiu,
        description: 'TCP/IP 分层模型、应用层协议与网络编程实践。',
        creditHours: 3,
        startDate: sem.startDate,
        endDate: sem.endDate,
        classIds: const ['cl_cn003_1'],
        color: 0xFFD49A3D,
        studentCount: 30,
        classCount: 1,
      ),
    ];
  }

  /// 4 个班级(高数 2 个班 + 数据结构 1 个 + 计算机网络 1 个)。
  static List<SchoolClass> get classes => [
        const SchoolClass(
          id: 'cl_hm001_1',
          courseId: 'c_hm001',
          name: '计科2024-1班',
          inviteCode: 'HM-A1X4',
          studentCount: 15,
          semester: '2024-2025-2',
          teacherId: 'u_teacher_demo',
          teacherName: '张明远',
          year: '2024级',
          major: '计算机科学与技术',
        ),
        const SchoolClass(
          id: 'cl_hm001_2',
          courseId: 'c_hm001',
          name: '计科2024-2班',
          inviteCode: 'HM-B7K2',
          studentCount: 15,
          semester: '2024-2025-2',
          teacherId: 'u_teacher_demo',
          teacherName: '张明远',
          year: '2024级',
          major: '计算机科学与技术',
        ),
        const SchoolClass(
          id: 'cl_ds002_1',
          courseId: 'c_ds002',
          name: '计科2024-1班',
          inviteCode: 'DS-C9P3',
          studentCount: 15,
          semester: '2024-2025-2',
          teacherId: 'u_teacher_demo',
          teacherName: '张明远',
          year: '2024级',
          major: '计算机科学与技术',
        ),
        const SchoolClass(
          id: 'cl_cn003_1',
          courseId: 'c_cn003',
          name: '计科2024-2班',
          inviteCode: 'CN-D5M8',
          studentCount: 15,
          semester: '2024-2025-2',
          teacherId: 'u_teacher_liu',
          teacherName: '刘文静',
          year: '2024级',
          major: '计算机科学与技术',
        ),
      ];

  /// 学生演示用户已加入的班级(用于 listStudentAssignments 等聚合查询)。
  static const List<String> studentJoinedClassIds = [
    'cl_hm001_1',
    'cl_ds002_1',
  ];

  // ===== 30 名学生(分布在高数1班15名 + 高数2班15名) =====

  static final List<String> _familyNames = [
    '李',
    '王',
    '张',
    '刘',
    '陈',
    '杨',
    '黄',
    '赵',
    '周',
    '吴',
    '徐',
    '孙',
    '马',
    '朱',
    '胡',
    '郭',
    '何',
    '高',
    '罗',
    '郑',
  ];
  static final List<String> _givenNames = [
    '思齐',
    '梓涵',
    '雨欣',
    '宇航',
    '佳怡',
    '俊杰',
    '若曦',
    '子轩',
    '欣怡',
    '浩然',
    '可昕',
    '彦霖',
    '梦瑶',
    '嘉豪',
    '雨彤',
  ];

  /// 生成 30 名学生(固定 ID,保证 demo 数据稳定)。
  /// 高数1班(15人)+ 高数2班(15人),共 30 人。
  /// 数据结构1班与高数1班共用同一批学生(便于跨课程统计)。
  static List<ClassMember> generateClassMembers() {
    final members = <ClassMember>[];
    for (var i = 0; i < 30; i++) {
      final familyIdx = i % _familyNames.length;
      final givenIdx = i % _givenNames.length;
      final name = '${_familyNames[familyIdx]}${_givenNames[givenIdx]}';
      final studentNo = '2024010${(101 + i).toString().padLeft(3, '0')}';
      final classId = i < 15 ? 'cl_hm001_1' : 'cl_hm001_2';
      final className = i < 15 ? '计科2024-1班' : '计科2024-2班';
      // 演示学生演示账号对应列表中的第一位(高数1班)
      final isDemoStudent = i == 0;

      // 演示数据:不同学生有不同的提交/已读状态
      final submitted =
          isDemoStudent ? 2 : (i % 3 == 0 ? 1 : (i % 5 == 0 ? 0 : 2));
      const total = 3;
      final overdue = (i % 7 == 0) ? 1 : 0;
      final graded = (i % 4 == 0) ? 1 : 0;
      final readCount = isDemoStudent ? 2 : (i % 2 == 0 ? 3 : 2);
      const readTotal = 4;
      final hasGrade = graded > 0;
      final grade = hasGrade ? (60 + (i % 5) * 8).toDouble() : null;
      final avgScore = (75 + (i % 10)).toDouble();

      members.add(
        ClassMember(
          userId: isDemoStudent
              ? 'u_student_demo'
              : 'u_student_${i.toString().padLeft(2, '0')}',
          studentId: studentNo,
          name: isDemoStudent ? '林知夏' : name,
          classId: classId,
          college: '计算机与人工智能学院',
          major: '计算机科学与技术',
          grade: '2024级',
          className: className,
          noticeReadCount: readCount,
          noticeTotalCount: readTotal,
          assignmentSubmittedCount: submitted,
          assignmentTotalCount: total,
          assignmentOverdueCount: overdue,
          assignmentGradedCount: graded,
          lastSubmissionAt: submitted > 0
              ? DateTime.now().subtract(Duration(hours: i))
              : null,
          lastReadAt: DateTime.now().subtract(Duration(hours: i + 1)),
          latestGrade: grade,
          averageScore: avgScore,
        ),
      );
    }
    return members;
  }

  // ===== 通知 =====

  /// 各班级的通知(教师发布给学生)。
  static List<Announcement> get announcements {
    final now = DateTime.now();
    return [
      Announcement(
        id: 'an_hm_001',
        classId: 'cl_hm001_1',
        courseId: 'c_hm001',
        title: '第 3 次作业截止时间调整通知',
        content: '各位同学:\n第 3 次作业《不定积分练习》的截止时间将由本周五 23:59 '
            '调整至下周一 23:59,请大家合理安排时间。\n如有疑问请在答疑时间到办公室咨询。',
        authorId: 'u_teacher_demo',
        authorName: '张明远',
        publishedAt: now.subtract(const Duration(hours: 5)),
        importance: NoticeImportance.important,
        tags: const ['作业', '截止调整'],
        read: false,
        readCount: 8,
        totalStudents: 15,
        aiSummary: '第 3 次作业截止时间从本周五延至下周一 23:59。',
        aiExtractedTasks: const [
          AnnouncementExtractedTask(
            title: '完成第 3 次作业《不定积分练习》',
            submissionMethod: '系统提交',
          ),
        ],
      ),
      Announcement(
        id: 'an_hm_002',
        classId: 'cl_hm001_1',
        courseId: 'c_hm001',
        title: '期中考试范围与时间安排',
        content: '期中考试定于第 10 周周五下午 14:00-16:00 在 A301 教室进行。'
            '考试范围:第 1-5 章内容(极限、连续、导数、微分中值定理、不定积分)。'
            '请同学们提前复习。允许携带计算器与一页 A4 笔记。',
        authorId: 'u_teacher_demo',
        authorName: '张明远',
        publishedAt: now.subtract(const Duration(days: 2)),
        importance: NoticeImportance.urgent,
        tags: const ['期中考试'],
        read: true,
        readCount: 15,
        totalStudents: 15,
        aiSummary: '期中考试:第 10 周周五 14:00 A301,范围 1-5 章,可带计算器和一页笔记。',
        aiExtractedTasks: const [
          AnnouncementExtractedTask(
            title: '准备期中考试',
            deadline: null,
            location: 'A301 教室',
            materials: ['计算器', '一页 A4 笔记'],
            submissionMethod: '现场考试',
          ),
        ],
      ),
      Announcement(
        id: 'an_ds_001',
        classId: 'cl_ds002_1',
        courseId: 'c_ds002',
        title: '链表实验报告提交说明',
        content: '请同学们在下周三 23:59 前提交单链表实验报告,'
            '内容包括:源代码(.java)、实验截图、运行结果分析。'
            '提交方式:课程系统附件上传,无需纸质版。',
        authorId: 'u_teacher_demo',
        authorName: '张明远',
        publishedAt: now.subtract(const Duration(hours: 18)),
        importance: NoticeImportance.normal,
        tags: const ['实验报告', '链表'],
        read: false,
        readCount: 5,
        totalStudents: 15,
        aiSummary: '链表实验报告下周三 23:59 前提交,需源码、截图、分析,系统附件上传。',
        aiExtractedTasks: const [
          AnnouncementExtractedTask(
            title: '提交链表实验报告',
            materials: ['源代码(.java)', '实验截图', '运行结果分析'],
            submissionMethod: '课程系统附件上传',
          ),
        ],
      ),
    ];
  }

  // ===== 任务 =====

  static List<Assignment> get assignments {
    final now = DateTime.now();
    return [
      Assignment(
        id: 'as_hm_hw1',
        classId: 'cl_hm001_1',
        courseId: 'c_hm001',
        title: '第 1 次作业:极限计算',
        description: '完成教材 P45 习题 1-10,需写出完整推导过程。',
        deadline: now.subtract(const Duration(days: 7)),
        createdAt: now.subtract(const Duration(days: 14)),
        authorId: 'u_teacher_demo',
        authorName: '张明远',
        submissionType: SubmissionType.text,
        allowResubmit: true,
        maxScore: 100,
        reminderLeadMinutes: 60,
        hasReminder: true,
        totalStudents: 15,
        submittedCount: 14,
        gradedCount: 12,
        overdueCount: 1,
        courseName: '高等数学',
        className: '计科2024-1班',
      ),
      Assignment(
        id: 'as_hm_hw2',
        classId: 'cl_hm001_1',
        courseId: 'c_hm001',
        title: '第 2 次作业:导数应用',
        description: '完成教材 P78 习题 1-8,涉及函数极值与最值问题。',
        deadline: now.add(const Duration(days: 2, hours: 8)),
        createdAt: now.subtract(const Duration(days: 7)),
        authorId: 'u_teacher_demo',
        authorName: '张明远',
        submissionType: SubmissionType.both,
        allowResubmit: true,
        maxScore: 100,
        reminderLeadMinutes: 60,
        hasReminder: true,
        totalStudents: 15,
        submittedCount: 9,
        gradedCount: 0,
        overdueCount: 0,
        courseName: '高等数学',
        className: '计科2024-1班',
      ),
      Assignment(
        id: 'as_hm_hw3',
        classId: 'cl_hm001_1',
        courseId: 'c_hm001',
        title: '第 3 次作业:不定积分练习',
        description: '完成教材 P102 习题 1-12,注意换元法与分部积分的应用。',
        deadline: now.add(const Duration(days: 4, hours: 12)),
        createdAt: now.subtract(const Duration(days: 3)),
        authorId: 'u_teacher_demo',
        authorName: '张明远',
        submissionType: SubmissionType.text,
        allowResubmit: true,
        maxScore: 100,
        reminderLeadMinutes: 120,
        hasReminder: true,
        totalStudents: 15,
        submittedCount: 3,
        gradedCount: 0,
        overdueCount: 0,
        courseName: '高等数学',
        className: '计科2024-1班',
      ),
      Assignment(
        id: 'as_ds_proj1',
        classId: 'cl_ds002_1',
        courseId: 'c_ds002',
        title: '链表实验:实现单链表基本操作',
        description: '实现单链表的插入、删除、查找、反转,并编写测试用例。'
            '提交内容:源代码(.java)、实验报告(.pdf)、运行截图。',
        deadline: now.add(const Duration(days: 5)),
        createdAt: now.subtract(const Duration(days: 10)),
        authorId: 'u_teacher_demo',
        authorName: '张明远',
        submissionType: SubmissionType.file,
        allowResubmit: false,
        maxScore: 100,
        reminderLeadMinutes: 60,
        hasReminder: true,
        totalStudents: 15,
        submittedCount: 7,
        gradedCount: 0,
        overdueCount: 0,
        courseName: '数据结构',
        className: '计科2024-1班',
      ),
    ];
  }

  // ===== 学生提交(演示账号 student_demo 的提交记录) =====

  static List<Submission> get studentDemoSubmissions {
    final now = DateTime.now();
    return [
      Submission(
        id: 'sub_001',
        assignmentId: 'as_hm_hw1',
        studentId: 'u_student_demo',
        studentName: '林知夏',
        studentNo: '2024010132',
        classId: 'cl_hm001_1',
        courseId: 'c_hm001',
        status: SubmissionStatus.graded,
        content: '习题 1: lim(x→0) sin(x)/x = 1 (利用重要极限)\n'
            '习题 2: lim(x→∞) (1+1/x)^x = e\n'
            '...(完整推导见附件)',
        submittedAt: now.subtract(const Duration(days: 9)),
        updatedAt: now.subtract(const Duration(days: 9)),
        grade: 92,
        comment: '推导清晰,第 7 题结论正确但过程可简化。',
        gradedAt: now.subtract(const Duration(days: 5)),
        gradedBy: 'u_teacher_demo',
        gradedByName: '张明远',
        resubmissionCount: 0,
        allowResubmit: true,
        isLate: false,
      ),
      Submission(
        id: 'sub_002',
        assignmentId: 'as_hm_hw2',
        studentId: 'u_student_demo',
        studentName: '林知夏',
        studentNo: '2024010132',
        classId: 'cl_hm001_1',
        courseId: 'c_hm001',
        status: SubmissionStatus.submitted,
        content: '已完成所有习题,详见附件。',
        attachments: const [
          Attachment(
            id: 'att_sub002_1',
            name: '高数作业2.pdf',
            sizeBytes: 1248000,
            mimeType: 'application/pdf',
            url: 'mock://attachments/sub002_1.pdf',
          ),
        ],
        submittedAt: now.subtract(const Duration(hours: 6)),
        updatedAt: now.subtract(const Duration(hours: 6)),
        resubmissionCount: 0,
        allowResubmit: true,
        isLate: false,
      ),
    ];
  }

  // ===== 教师视角:所有提交(高数1班所有学生) =====

  /// 生成 15 名学生在第 2 次作业(as_hm_hw2)上的提交摘要。
  /// 9 人已提交,6 人未提交(用于教师统计页演示)。
  static List<StudentStatus> generateHw2StudentStatuses() {
    final list = <StudentStatus>[];
    for (var i = 0; i < 15; i++) {
      final name = i == 0
          ? '林知夏'
          : '${_familyNames[i % _familyNames.length]}${_givenNames[i % _givenNames.length]}';
      final studentNo = '2024010${(101 + i).toString().padLeft(3, '0')}';
      final submitted = i < 9; // 前 9 人已提交
      list.add(
        StudentStatus(
          studentId: i == 0
              ? 'u_student_demo'
              : 'u_student_${i.toString().padLeft(2, '0')}',
          name: name,
          studentNo: studentNo,
          classId: 'cl_hm001_1',
          className: '计科2024-1班',
          status: submitted
              ? (i < 3 ? SubmissionStatus.graded : SubmissionStatus.submitted)
              : SubmissionStatus.notSubmitted,
          submittedAt: submitted
              ? DateTime.now().subtract(Duration(hours: i + 1))
              : null,
          grade: submitted && i < 3 ? (85 + i * 3).toDouble() : null,
          hasAttachment: submitted && i % 2 == 0,
          attachmentCount: submitted && i % 2 == 0 ? 1 : 0,
          contentLength: submitted ? 250 + i * 30 : 0,
        ),
      );
    }
    return list;
  }

  /// 高数第 2 次作业的所有提交(教师查看已交列表用)。
  static List<Submission> generateHw2Submissions() {
    final list = <Submission>[];
    final statuses = generateHw2StudentStatuses();
    for (var i = 0; i < 9; i++) {
      final s = statuses[i];
      list.add(
        Submission(
          id: 'sub_hw2_${i.toString().padLeft(2, '0')}',
          assignmentId: 'as_hm_hw2',
          studentId: s.studentId,
          studentName: s.name,
          studentNo: s.studentNo,
          classId: 'cl_hm001_1',
          courseId: 'c_hm001',
          status: s.status,
          content: '本次作业完成情况:\n${s.contentLength > 0 ? "详见推导过程..." : "提交简短回答"}',
          attachments: s.hasAttachment
              ? [
                  Attachment(
                    id: 'att_hw2_$i',
                    name: '高数作业2.pdf',
                    sizeBytes: 1100000 + i * 50000,
                    mimeType: 'application/pdf',
                    url: 'mock://attachments/hw2_$i.pdf',
                  ),
                ]
              : const [],
          submittedAt: s.submittedAt!,
          updatedAt: s.submittedAt,
          grade: s.grade,
          comment: s.grade != null ? '推导清晰,步骤规范。' : null,
          gradedAt: s.grade != null
              ? DateTime.now().subtract(const Duration(hours: 2))
              : null,
          gradedBy: s.grade != null ? 'u_teacher_demo' : null,
          gradedByName: s.grade != null ? '张明远' : null,
          resubmissionCount: 0,
          allowResubmit: true,
          isLate: false,
        ),
      );
    }
    return list;
  }

  /// 教师最近活动。
  static List<TeacherActivity> get teacherRecentActivities {
    final now = DateTime.now();
    return [
      TeacherActivity(
        id: 'act_1',
        label: '林知夏 提交了《第 2 次作业:导数应用》',
        timestamp: now.subtract(const Duration(hours: 6)),
        actionType: NextActionType.gradeSubmission,
        targetPath: '/teacher/stats/as_hm_hw2',
      ),
      TeacherActivity(
        id: 'act_2',
        label: '发布了通知《第 3 次作业截止时间调整通知》',
        timestamp: now.subtract(const Duration(hours: 5)),
        actionType: NextActionType.publishAnnouncement,
      ),
      TeacherActivity(
        id: 'act_3',
        label: '王梓涵 提交了《第 2 次作业:导数应用》',
        timestamp: now.subtract(const Duration(hours: 8)),
        actionType: NextActionType.gradeSubmission,
        targetPath: '/teacher/stats/as_hm_hw2',
      ),
      TeacherActivity(
        id: 'act_4',
        label: '创建了课程《数据结构》',
        timestamp: now.subtract(const Duration(days: 2)),
        actionType: NextActionType.other,
      ),
    ];
  }

  /// 教师下一步行动(基于演示数据派生)。
  static List<TeacherNextAction> get teacherNextActions => [
        const TeacherNextAction(
          id: 'na_grade_hw2',
          label: '9 份提交待查看',
          actionType: NextActionType.gradeSubmission,
          count: 9,
          targetPath: '/teacher/stats/as_hm_hw2',
          priority: NextActionPriority.high,
        ),
        const TeacherNextAction(
          id: 'na_remind_hw3',
          label: '12 名学生尚未提交《第 3 次作业》',
          actionType: NextActionType.remindUnsubmitted,
          count: 12,
          targetPath: '/teacher/stats/as_hm_hw3',
          priority: NextActionPriority.normal,
        ),
        const TeacherNextAction(
          id: 'na_unread_notice',
          label: '7 名学生未读通知',
          actionType: NextActionType.remindUnread,
          count: 7,
          priority: NextActionPriority.low,
        ),
      ];
}

/// 演示账号(用于登录页快捷登录)。
class DemoAccount {
  const DemoAccount({
    required this.username,
    required this.password,
    required this.role,
    required this.displayName,
    required this.subtitle,
  });

  final String username;
  final String password;
  final UserRole role;
  final String displayName;
  final String subtitle;
}
