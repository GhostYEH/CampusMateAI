import { describe, expect, it } from '@ohos/hypium';
import { AppRoute, AppRouteRegistry } from '../../../main/ets/navigation/AppRoute';

export default function appRouteTest(): void {
  describe('AppRoute', () => {
    it('recognizes every retained secondary destination', 0, () => {
      const routes: string[] = [
        AppRoute.EXAMS,
        AppRoute.CLASSROOMS,
        AppRoute.UNIVERSITY,
        AppRoute.COMMUNITY,
        AppRoute.COMMUNITY_HOT,
        AppRoute.COMMUNITY_PUBLISH,
        AppRoute.COMMUNITY_DETAIL,
        AppRoute.COMMUNITY_EDIT,
        AppRoute.ACADEMIC,
        AppRoute.FOCUS,
        AppRoute.LOST_FOUND,
        AppRoute.NOTIFICATIONS,
        AppRoute.NOTIFICATION_SOURCE_SETTINGS,
        AppRoute.CHAOXING,
        AppRoute.FILES,
        AppRoute.ACTIVITIES,
        AppRoute.FAVORITES,
        AppRoute.SETTINGS,
        AppRoute.QR_SCANNER,
        AppRoute.QR_CONFIRM,
        AppRoute.ACCOUNT,
        AppRoute.EDU_SYSTEM,
        AppRoute.EDU_LOGIN,
        AppRoute.EDU_SCHEDULE,
        AppRoute.ABOUT,
        AppRoute.COURSE_DETAIL,
        AppRoute.TASK_DETAIL,
        AppRoute.EXAM_DETAIL,
        AppRoute.EXAM_FORM,
        AppRoute.LOST_FOUND_DETAIL,
        AppRoute.LOST_FOUND_PUBLISH,
        AppRoute.LOST_FOUND_MINE,
        AppRoute.NOTIFICATION_DETAIL,
        AppRoute.EDU_SCHEDULE_DETAIL
      ];

      for (let index: number = 0; index < routes.length; index++) {
        expect(AppRouteRegistry.isSecondary(routes[index])).assertEqual(true);
        expect(AppRouteRegistry.title(routes[index]).length > 0).assertEqual(true);
      }
      expect(AppRouteRegistry.isSecondary('missing-route')).assertEqual(false);
      expect(AppRouteRegistry.title('missing-route')).assertEqual('校园服务');
    });

    it('models nested flows with their real back destination', 0, () => {
      expect(AppRouteRegistry.parent(AppRoute.COMMUNITY_HOT)).assertEqual(AppRoute.COMMUNITY);
      expect(AppRouteRegistry.parent(AppRoute.COMMUNITY_PUBLISH)).assertEqual(AppRoute.COMMUNITY);
      expect(AppRouteRegistry.parent(AppRoute.COMMUNITY_DETAIL)).assertEqual(AppRoute.COMMUNITY);
      expect(AppRouteRegistry.parent(AppRoute.COMMUNITY_EDIT)).assertEqual(AppRoute.COMMUNITY_DETAIL);
      expect(AppRouteRegistry.parent(AppRoute.QR_CONFIRM)).assertEqual(AppRoute.QR_SCANNER);
      expect(AppRouteRegistry.parent(AppRoute.EDU_LOGIN)).assertEqual(AppRoute.EDU_SYSTEM);
      expect(AppRouteRegistry.parent(AppRoute.EDU_SCHEDULE)).assertEqual(AppRoute.EDU_SYSTEM);
      expect(AppRouteRegistry.parent(AppRoute.NOTIFICATION_SOURCE_SETTINGS)).assertEqual(AppRoute.NOTIFICATIONS);
      expect(AppRouteRegistry.parent(AppRoute.CHAOXING)).assertEqual(AppRoute.NOTIFICATIONS);
      expect(AppRouteRegistry.parent(AppRoute.COURSE_DETAIL)).assertEqual('courses');
      expect(AppRouteRegistry.parent(AppRoute.TASK_DETAIL)).assertEqual('tasks');
      expect(AppRouteRegistry.parent(AppRoute.EXAM_DETAIL)).assertEqual(AppRoute.EXAMS);
      expect(AppRouteRegistry.parent(AppRoute.EXAM_FORM)).assertEqual(AppRoute.EXAMS);
      expect(AppRouteRegistry.parent(AppRoute.LOST_FOUND_DETAIL)).assertEqual(AppRoute.LOST_FOUND);
      expect(AppRouteRegistry.parent(AppRoute.LOST_FOUND_PUBLISH)).assertEqual(AppRoute.LOST_FOUND);
      expect(AppRouteRegistry.parent(AppRoute.LOST_FOUND_MINE)).assertEqual(AppRoute.LOST_FOUND);
      expect(AppRouteRegistry.parent(AppRoute.NOTIFICATION_DETAIL)).assertEqual(AppRoute.NOTIFICATIONS);
      expect(AppRouteRegistry.parent(AppRoute.EDU_SCHEDULE_DETAIL)).assertEqual(AppRoute.EDU_SCHEDULE);
      expect(AppRouteRegistry.parent(AppRoute.EXAMS)).assertEqual('');
    });

    it('keeps primary destinations in the five-tab shell', 0, () => {
      expect(AppRouteRegistry.tabIndex('home')).assertEqual(0);
      expect(AppRouteRegistry.tabIndex('courses')).assertEqual(1);
      expect(AppRouteRegistry.tabIndex('tasks')).assertEqual(2);
      expect(AppRouteRegistry.tabIndex('counselor')).assertEqual(3);
      expect(AppRouteRegistry.tabIndex('profile')).assertEqual(4);
      expect(AppRouteRegistry.tabIndex(AppRoute.EXAMS)).assertEqual(-1);
      expect(AppRouteRegistry.tabIndex('missing-route')).assertEqual(-1);
    });

    it('loads data only for destinations backed by a list or status request', 0, () => {
      expect(AppRouteRegistry.loadsOnOpen(AppRoute.EXAMS)).assertEqual(true);
      expect(AppRouteRegistry.loadsOnOpen(AppRoute.COMMUNITY)).assertEqual(true);
      expect(AppRouteRegistry.loadsOnOpen(AppRoute.NOTIFICATIONS)).assertEqual(true);
      expect(AppRouteRegistry.loadsOnOpen(AppRoute.CHAOXING)).assertEqual(true);
      expect(AppRouteRegistry.loadsOnOpen(AppRoute.FILES)).assertEqual(true);
      expect(AppRouteRegistry.loadsOnOpen(AppRoute.COMMUNITY_HOT)).assertEqual(false);
      expect(AppRouteRegistry.loadsOnOpen(AppRoute.COMMUNITY_DETAIL)).assertEqual(false);
      expect(AppRouteRegistry.loadsOnOpen(AppRoute.QR_CONFIRM)).assertEqual(false);
      expect(AppRouteRegistry.loadsOnOpen(AppRoute.ABOUT)).assertEqual(false);
    });
  });
}
