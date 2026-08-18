import { CampusTask, Course, Notice, User } from './types'

export const demoUsers: Record<string, User> = {
  student_demo: {
    name: '林知夏',
    role: 'student',
    detail: '计算机科学与技术 · 大三',
    email: 'lin.zhixia@campus.edu.cn',
    studentId: '2024020318',
    universityId: '',
    universityName: '',
  },
}

export const defaultTasks: CampusTask[] = [
  { id: 1, title: '《数据结构》作业三：链表与栈', due: '今天 23:59', course: '课程作业', done: false },
  { id: 2, title: '《高等数学》习题课报告提交', due: '明天 20:00', course: '课程作业', done: false },
  { id: 3, title: '整理创新创业项目资料', due: '8月5日 18:00', course: '个人待办', done: false },
  { id: 4, title: '图书馆座位预约', due: '今天 14:00', course: '学习安排', done: true },
]

export const defaultNotices: Notice[] = [
  { id: 1, title: '关于开展暑期社会实践活动的通知', source: '学生事务', time: '10:15', unread: true },
  { id: 2, title: '第十六届程序设计竞赛报名通知', source: '创新实践中心', time: '昨天', unread: true },
  { id: 3, title: '期末考试安排及相关事项说明', source: '教务处', time: '7月29日', unread: false },
  { id: 4, title: '图书馆数据库试用资源更新通知', source: '图书馆', time: '7月28日', unread: false },
]

export const defaultCourses: Course[] = [
  { name: '数据结构', code: 'CS2103', type: '专业必修', teacher: '张明远', location: '教学楼 2-305', weekday: '周一', time: '10:00–11:40' },
  { name: '计算机组成原理', code: 'CS2201', type: '专业必修', teacher: '刘文青', location: '实验楼 A-204', weekday: '周二', time: '14:00–15:40' },
  { name: '高等数学（下）', code: 'MA1202', type: '学科基础', teacher: '王建国', location: '博学楼 1-401', weekday: '周三', time: '08:00–09:40' },
  { name: '大学英语 IV', code: 'EN1404', type: '公共基础', teacher: '陈思雨', location: '明德楼 3-208', weekday: '周四', time: '10:00–11:40' },
  { name: '操作系统原理', code: 'CS2304', type: '专业核心', teacher: '赵启航', location: '教学楼 4-302', weekday: '周五', time: '14:00–15:40' },
  { name: '计算机网络', code: 'CS2402', type: '专业核心', teacher: '周立新', location: '实验楼 B-310', weekday: '周五', time: '16:00–17:40' },
]
