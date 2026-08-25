import { describe, expect, it } from '@ohos/hypium';
import {
  allowedOriginsFromEduResponse,
  cookieDtosForUrl,
  isAllowedEduNavigation
} from '../../../main/ets/features/edu/EduLoginSecurity';
import {
  EduLoginSensitiveEvent,
  EduLoginSensitiveState,
  reduceEduLoginSensitiveState
} from '../../../main/ets/features/edu/EduLoginSensitiveState';

export default function eduLoginSecurityTest(): void {
  describe('EduLoginSecurity', () => {
    it('clears sensitive login fields for every lifecycle exit and keeps username', 0, () => {
      const events: EduLoginSensitiveEvent[] = [
        EduLoginSensitiveEvent.DIRECT_CONNECTED,
        EduLoginSensitiveEvent.WEB_HANDOFF,
        EduLoginSensitiveEvent.DISCONNECT,
        EduLoginSensitiveEvent.CONNECTION_REPLACED,
        EduLoginSensitiveEvent.CANCEL,
        EduLoginSensitiveEvent.DISPOSE
      ];
      const initial: EduLoginSensitiveState = {
        username: 'student-1',
        password: 'secret',
        captcha: '1234',
        preLoginToken: 'pre-login-token'
      };

      for (let index = 0; index < events.length; index++) {
        const result: EduLoginSensitiveState = reduceEduLoginSensitiveState(initial, events[index]);
        expect(result.username).assertEqual('student-1');
        expect(result.password).assertEqual('');
        expect(result.captcha).assertEqual('');
        expect(result.preLoginToken === undefined).assertTrue();
      }
    });

    it('preserves allowed origins from the backend connection response', 0, () => {
      expect(allowedOriginsFromEduResponse({ allowed_origins: ['https://sso.huel.edu.cn'] })[0])
        .assertEqual('https://sso.huel.edu.cn');
      expect(allowedOriginsFromEduResponse({}).length).assertEqual(0);
    });

    it('allows only exact HTTPS login and backend-listed origins', 0, () => {
      const loginUrl: string = 'https://xk.huel.edu.cn/jwglxt/xtgl/login_slogin.html';
      expect(isAllowedEduNavigation('https://xk.huel.edu.cn/jwglxt/xsxx', loginUrl)).assertTrue();
      expect(isAllowedEduNavigation('https://sso.huel.edu.cn/cas/login', loginUrl, ['https://sso.huel.edu.cn'])).assertTrue();
      expect(isAllowedEduNavigation('http://xk.huel.edu.cn/jwglxt', loginUrl)).assertFalse();
      expect(isAllowedEduNavigation('https://xk.huel.edu.cn.attacker.example/login', loginUrl)).assertFalse();
      expect(isAllowedEduNavigation('weixin://dl/business', loginUrl)).assertFalse();
    });

    it('keeps same-name cookies from distinct origins as separate DTOs', 0, () => {
      const cookies = cookieDtosForUrl('JSESSIONID=portal', 'https://xk.huel.edu.cn/jwglxt')
        .concat(cookieDtosForUrl('JSESSIONID=sso', 'https://sso.huel.edu.cn/cas'));
      expect(cookies.length).assertEqual(2);
      expect(cookies[0].domain).assertEqual('xk.huel.edu.cn');
      expect(cookies[1].domain).assertEqual('sso.huel.edu.cn');
      expect(cookies[0].secure === undefined).assertTrue();
    });
  });
}
