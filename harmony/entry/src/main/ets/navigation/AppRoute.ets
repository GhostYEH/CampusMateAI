export enum AppRoute {
  EXAMS = 'exams',
  CLASSROOMS = 'classrooms',
  UNIVERSITY = 'university',
  COMMUNITY = 'community',
  COMMUNITY_HOT = 'community_hot',
  COMMUNITY_PUBLISH = 'community_publish',
  COMMUNITY_DETAIL = 'community_detail',
  COMMUNITY_EDIT = 'community_edit',
  ACADEMIC = 'academic',
  FOCUS = 'focus',
  FOCUS_PLAN = 'focus_plan',
  FOCUS_SESSION = 'focus_session',
  FOCUS_SUMMARY = 'focus_summary',
  LOST_FOUND = 'lostfound',
  NOTIFICATIONS = 'notifications',
  NOTIFICATION_SOURCE_SETTINGS = 'notification_source_settings',
  CHAOXING = 'chaoxing',
  FILES = 'files',
  FAVORITES = 'favorites',
  SETTINGS = 'settings',
  QR_SCANNER = 'qr_scanner',
  QR_CONFIRM = 'qr_confirm',
  ACCOUNT = 'account',
  EDU_SYSTEM = 'edu_system',
  EDU_LOGIN = 'edu_login',
  EDU_SCHEDULE = 'edu_schedule',
  ABOUT = 'about',
  COURSE_DETAIL = 'course_detail',
  TASK_DETAIL = 'task_detail',
  EXAM_DETAIL = 'exam_detail',
  EXAM_FORM = 'exam_form',
  LOST_FOUND_DETAIL = 'lostfound_detail',
  LOST_FOUND_PUBLISH = 'lostfound_publish',
  LOST_FOUND_MINE = 'lostfound_mine',
  NOTIFICATION_DETAIL = 'notification_detail',
  EDU_SCHEDULE_DETAIL = 'edu_schedule_detail'
}

export class AppRouteRegistry {
  static tabIndex(route: string): number {
    switch (route) {
      case 'home': return 0;
      case 'courses': return 1;
      case 'tasks': return 2;
      case 'counselor': return 3;
      case 'profile': return 4;
      default: return -1;
    }
  }

  static isSecondary(route: string): boolean {
    switch (route) {
      case AppRoute.EXAMS:
      case AppRoute.CLASSROOMS:
      case AppRoute.UNIVERSITY:
      case AppRoute.COMMUNITY:
      case AppRoute.COMMUNITY_HOT:
      case AppRoute.COMMUNITY_PUBLISH:
      case AppRoute.COMMUNITY_DETAIL:
      case AppRoute.COMMUNITY_EDIT:
      case AppRoute.ACADEMIC:
      case AppRoute.FOCUS:
      case AppRoute.FOCUS_PLAN:
      case AppRoute.FOCUS_SESSION:
      case AppRoute.FOCUS_SUMMARY:
      case AppRoute.LOST_FOUND:
      case AppRoute.NOTIFICATIONS:
      case AppRoute.NOTIFICATION_SOURCE_SETTINGS:
      case AppRoute.CHAOXING:
      case AppRoute.FILES:
      case AppRoute.FAVORITES:
      case AppRoute.SETTINGS:
      case AppRoute.QR_SCANNER:
      case AppRoute.QR_CONFIRM:
      case AppRoute.ACCOUNT:
      case AppRoute.EDU_SYSTEM:
      case AppRoute.EDU_LOGIN:
      case AppRoute.EDU_SCHEDULE:
      case AppRoute.ABOUT:
      case AppRoute.COURSE_DETAIL:
      case AppRoute.TASK_DETAIL:
      case AppRoute.EXAM_DETAIL:
      case AppRoute.EXAM_FORM:
      case AppRoute.LOST_FOUND_DETAIL:
      case AppRoute.LOST_FOUND_PUBLISH:
      case AppRoute.LOST_FOUND_MINE:
      case AppRoute.NOTIFICATION_DETAIL:
      case AppRoute.EDU_SCHEDULE_DETAIL:
        return true;
      default:
        return false;
    }
  }

  static loadsOnOpen(route: string): boolean {
    switch (route) {
      case AppRoute.EXAMS:
      case AppRoute.CLASSROOMS:
      case AppRoute.UNIVERSITY:
      case AppRoute.COMMUNITY:
      case AppRoute.ACADEMIC:
      case AppRoute.FOCUS:
      case AppRoute.LOST_FOUND:
      case AppRoute.NOTIFICATIONS:
      case AppRoute.CHAOXING:
      case AppRoute.FILES:
      case AppRoute.FAVORITES:
        return true;
      default:
        return false;
    }
  }

  static title(route: string): string {
    switch (route) {
      case AppRoute.EXAMS: return '考试安排';
      case AppRoute.CLASSROOMS: return '空教室查询';
      case AppRoute.UNIVERSITY: return '我的大学';
      case AppRoute.COMMUNITY: return '校园社区';
      case AppRoute.COMMUNITY_HOT: return '热门话题';
      case AppRoute.COMMUNITY_PUBLISH: return '发布帖子';
      case AppRoute.COMMUNITY_DETAIL: return '帖子详情';
      case AppRoute.COMMUNITY_EDIT: return '编辑帖子';
      case AppRoute.ACADEMIC: return '教务系统';
      case AppRoute.FOCUS: return '专注自习';
      case AppRoute.FOCUS_PLAN: return '任务规划';
      case AppRoute.FOCUS_SESSION: return '专注空间';
      case AppRoute.FOCUS_SUMMARY: return '本次专注总结';
      case AppRoute.LOST_FOUND: return '失物招领';
      case AppRoute.NOTIFICATIONS: return '通知与提醒';
      case AppRoute.NOTIFICATION_SOURCE_SETTINGS: return '通知来源设置';
      case AppRoute.CHAOXING: return '学习通';
      case AppRoute.FILES: return '我的文件';
      case AppRoute.FAVORITES: return '我的收藏';
      case AppRoute.SETTINGS: return '系统设置';
      case AppRoute.QR_SCANNER: return '扫一扫';
      case AppRoute.QR_CONFIRM: return '确认登录';
      case AppRoute.ACCOUNT: return '账号与隐私';
      case AppRoute.EDU_SYSTEM: return '教务系统';
      case AppRoute.EDU_LOGIN: return '登录教务系统';
      case AppRoute.EDU_SCHEDULE: return '我的课表';
      case AppRoute.ABOUT: return '关于 CampusMate';
      case AppRoute.COURSE_DETAIL: return '课程详情';
      case AppRoute.TASK_DETAIL: return '待办详情';
      case AppRoute.EXAM_DETAIL: return '考试详情';
      case AppRoute.EXAM_FORM: return '编辑考试';
      case AppRoute.LOST_FOUND_DETAIL: return '失物招领详情';
      case AppRoute.LOST_FOUND_PUBLISH: return '发布失物招领';
      case AppRoute.LOST_FOUND_MINE: return '我的发布';
      case AppRoute.NOTIFICATION_DETAIL: return '通知详情';
      case AppRoute.EDU_SCHEDULE_DETAIL: return '课程详情';
      default: return '校园服务';
    }
  }

  static parent(route: string): string {
    switch (route) {
      case AppRoute.COMMUNITY_HOT:
      case AppRoute.COMMUNITY_PUBLISH:
      case AppRoute.COMMUNITY_DETAIL:
        return AppRoute.COMMUNITY;
      case AppRoute.COMMUNITY_EDIT:
        return AppRoute.COMMUNITY_DETAIL;
      case AppRoute.QR_CONFIRM:
        return AppRoute.QR_SCANNER;
      case AppRoute.EDU_LOGIN:
      case AppRoute.EDU_SCHEDULE:
        return AppRoute.EDU_SYSTEM;
      case AppRoute.NOTIFICATION_SOURCE_SETTINGS:
      case AppRoute.CHAOXING:
        return AppRoute.NOTIFICATIONS;
      case AppRoute.COURSE_DETAIL:
        return 'courses';
      case AppRoute.TASK_DETAIL:
        return 'tasks';
      case AppRoute.EXAM_DETAIL:
      case AppRoute.EXAM_FORM:
        return AppRoute.EXAMS;
      case AppRoute.LOST_FOUND_DETAIL:
      case AppRoute.LOST_FOUND_PUBLISH:
      case AppRoute.LOST_FOUND_MINE:
        return AppRoute.LOST_FOUND;
      case AppRoute.NOTIFICATION_DETAIL:
        return AppRoute.NOTIFICATIONS;
      case AppRoute.EDU_SCHEDULE_DETAIL:
        return AppRoute.EDU_SCHEDULE;
      case AppRoute.FOCUS_SESSION:
      case AppRoute.FOCUS_SUMMARY:
      case AppRoute.FOCUS_PLAN:
        return AppRoute.FOCUS;
      default:
        return '';
    }
  }
}
