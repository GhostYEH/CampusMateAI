const STORAGE_KEY = "campus_portal_mock_v1";

const seed = {
  courses: [
    { id: "course_ds", name: "数据结构", code: "CS204", semester: "2026 秋季", status: "active", teacher_name: "张明远" },
    { id: "course_cn", name: "计算机网络", code: "CS306", semester: "2026 秋季", status: "active", teacher_name: "张明远" },
    { id: "course_se", name: "软件工程实践", code: "CS318", semester: "2026 秋季", status: "active", teacher_name: "张明远" },
  ],
  classes: [
    { id: "class_ds1", course_id: "course_ds", name: "计科 2401 班", class_code: "CS2401", capacity: 42 },
    { id: "class_ds2", course_id: "course_ds", name: "软件 2402 班", class_code: "SE2402", capacity: 38 },
    { id: "class_cn1", course_id: "course_cn", name: "计科 2301 班", class_code: "CS2301", capacity: 45 },
    { id: "class_se1", course_id: "course_se", name: "软件 2301 班", class_code: "SE2301", capacity: 40 },
  ],
  assignments: [
    { id: "asg_1", class_group_id: "class_ds1", title: "链表与栈综合练习", description: "完成实验指导书第 3 章，并提交源代码与实验报告。", deadline: "2026-08-03T23:59:00+08:00", max_score: 100, status: "published", submitted_count: 36, student_count: 42 },
    { id: "asg_2", class_group_id: "class_ds2", title: "二叉树遍历实验", description: "实现先序、中序和后序遍历，说明时间复杂度。", deadline: "2026-08-08T20:00:00+08:00", max_score: 100, status: "published", submitted_count: 21, student_count: 38 },
    { id: "asg_3", class_group_id: "class_cn1", title: "抓包分析报告", description: "使用 Wireshark 观察 TCP 三次握手并完成分析。", deadline: "2026-08-12T23:59:00+08:00", max_score: 100, status: "draft", submitted_count: 0, student_count: 45 },
    { id: "asg_4", class_group_id: "class_se1", title: "需求访谈纪要", description: "以小组为单位提交访谈提纲、原始记录和结论。", deadline: "2026-08-01T18:00:00+08:00", max_score: 50, status: "closed", submitted_count: 38, student_count: 40 },
  ],
  activities: [
    { id: "act_1", title: "暑期社会实践项目成果展", summary: "看看不同学院的同学如何把专业所学带进社区与乡村。", content: "现场设有项目路演、成果海报展示与优秀团队交流环节。", category: "volunteer", location: "大学生活动中心一楼", registration_deadline: "2026-08-18T18:00:00+08:00", starts_at: "2026-08-20T14:00:00+08:00", capacity: 300, status: "published", published_at: "2026-07-28T10:30:00+08:00" },
    { id: "act_2", title: "人工智能与校园创新应用讲座", summary: "从真实校园问题出发，了解 AI 产品设计与工程落地。", content: "讲座包含主题分享与开放问答，报名后请留意站内通知。", category: "lecture", location: "图书馆报告厅", registration_deadline: "2026-08-25T12:00:00+08:00", starts_at: "2026-08-27T19:00:00+08:00", capacity: 220, status: "published", published_at: "2026-07-29T14:20:00+08:00" },
    { id: "act_3", title: "新生志愿服务队招募", summary: "参与迎新引导、校园咨询与物资协助。", content: "完成培训后按岗位排班，服务时长计入志愿服务记录。", category: "volunteer", location: "学生事务中心", registration_deadline: "2026-09-01T18:00:00+08:00", starts_at: "2026-09-03T09:00:00+08:00", capacity: 120, status: "draft", published_at: null },
  ],
  users: [
    { id: "u_s1", username: "student_demo", display_name: "林知夏", student_number: "2024010132", role: "student", college: "计算机学院", major: "计算机科学与技术", grade: "2024", is_active: true, created_at: "2026-03-02T09:00:00+08:00" },
    { id: "u_s2", username: "zhou_yuchen", display_name: "周予辰", student_number: "2024010108", role: "student", college: "计算机学院", major: "软件工程", grade: "2024", is_active: true, created_at: "2026-03-02T09:05:00+08:00" },
    { id: "u_s3", username: "chen_yinuo", display_name: "陈一诺", student_number: "2023010206", role: "student", college: "计算机学院", major: "计算机科学与技术", grade: "2023", is_active: false, created_at: "2026-03-02T09:10:00+08:00" },
    { id: "u_t1", username: "teacher_demo", display_name: "张明远", teacher_number: "T20180456", role: "teacher", college: "计算机学院", major: "计算机系", is_active: true, created_at: "2026-02-20T10:00:00+08:00" },
    { id: "u_t2", username: "liu_wenjing", display_name: "刘文静", teacher_number: "T20170628", role: "teacher", college: "外国语学院", major: "大学英语教学部", is_active: true, created_at: "2026-02-21T10:00:00+08:00" },
    { id: "u_a1", username: "admin_demo", display_name: "系统管理员", role: "admin", college: "信息中心", is_active: true, created_at: "2026-01-10T08:00:00+08:00" },
  ],
};

export function loadMockPortal() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    try { return JSON.parse(saved); } catch { /* 使用初始演示数据 */ }
  }
  const initial = structuredClone(seed);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(initial));
  return initial;
}

export function saveMockPortal(data) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

