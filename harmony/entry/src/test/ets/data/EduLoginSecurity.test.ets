import { describe, expect, it } from '@ohos/hypium';
import { cookieDtosForUrl, isAllowedEduNavigation } from '../../../main/ets/features/edu/EduLoginSecurity';

export default function eduLoginSecurityTest(): void {
  describe('EduLoginSecurity', () => {
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
