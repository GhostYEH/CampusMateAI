import { describe, expect, it } from '@ohos/hypium';
import { EduConnectionDto, EduPreLoginResult } from '../../../main/ets/data/ApiClient';
import {
  allowedOriginsFromEduResponse,
  cookieDtosForUrl,
  isAllowedEduNavigation
} from '../../../main/ets/features/edu/EduLoginSecurity';
import {
  captureEduLoginChallenge,
  EduLoginSensitiveEvent,
  EduLoginSensitiveState,
  reduceEduLoginSensitiveState
} from '../../../main/ets/features/edu/EduLoginSensitiveState';
import {
  EduConnectionRequestGuard,
  EduConnectionRequestToken
} from '../../../main/ets/features/edu/EduConnectionRequestGuard';
import {
  EduLoginSurface,
  selectEduLoginSurface
} from '../../../main/ets/features/edu/EduLoginSurface';

export default function eduLoginSecurityTest(): void {
  describe('EduLoginSecurity', () => {
    it('captures the real captcha challenge in lifecycle-cleared state', 0, () => {
      const captured: EduLoginSensitiveState = captureEduLoginChallenge({
        username: 'student-1', password: 'secret', captcha: '', preLoginToken: undefined
      }, '1234', 'pre-login-token');
      expect(captured.captcha).assertEqual('1234');
      expect(captured.preLoginToken).assertEqual('pre-login-token');
      const cleared = reduceEduLoginSensitiveState(captured, EduLoginSensitiveEvent.DIRECT_CONNECTED);
      expect(cleared.password).assertEqual('');
      expect(cleared.captcha).assertEqual('');
      expect(cleared.preLoginToken === undefined).assertTrue();
    });

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
      const connection: EduConnectionDto = {
        id: 'connection-1', state: 'waiting_user_login', provider: 'zhengfang',
        login_execution_mode: 'client_webview', allowed_origins: ['https://sso.huel.edu.cn']
      };
      const legacyConnection: EduConnectionDto = {
        id: 'connection-2', state: 'waiting_user_login', provider: 'zhengfang',
        login_execution_mode: 'client_webview'
      };
      expect(allowedOriginsFromEduResponse(connection)[0])
        .assertEqual('https://sso.huel.edu.cn');
      expect(allowedOriginsFromEduResponse(legacyConnection).length).assertEqual(0);
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

    it('does not let a delayed request from a replaced connection overwrite current state', 0, async () => {
      const guard: EduConnectionRequestGuard = new EduConnectionRequestGuard();
      const oldGeneration: number = guard.beginReplacement();
      expect(guard.acceptCreatedConnection(oldGeneration, 'connection-old')).assertTrue();
      const oldRequest: EduConnectionRequestToken | undefined = guard.capture('connection-old');
      expect(oldRequest !== undefined).assertTrue();

      const delayedOldResult: Promise<string> = (async (): Promise<string> => {
        await Promise.resolve();
        return 'connection-old';
      })();
      const newGeneration: number = guard.beginReplacement();
      expect(guard.acceptCreatedConnection(newGeneration, 'connection-new')).assertTrue();
      let renderedConnectionId: string = 'connection-new';
      let renderedCaptcha: string = 'new-answer';
      let renderedPreLoginToken: string = 'new-token';

      const oldResultId: string = await delayedOldResult;
      guard.commitIfCurrent(oldRequest as EduConnectionRequestToken, oldResultId, () => {
        renderedConnectionId = oldResultId;
        renderedCaptcha = 'old-answer';
        renderedPreLoginToken = 'old-token';
      });

      expect(renderedConnectionId).assertEqual('connection-new');
      expect(renderedCaptcha).assertEqual('new-answer');
      expect(renderedPreLoginToken).assertEqual('new-token');
    });

    it('selects exactly one credentials or captcha surface for backend login', 0, () => {
      const backendConnection: EduConnectionDto = {
        id: 'connection-backend', state: 'waiting_user_login', provider: 'zhengfang',
        login_execution_mode: 'backend_http'
      };
      const clientConnection: EduConnectionDto = {
        id: 'connection-client', state: 'waiting_user_login', provider: 'zhengfang',
        login_execution_mode: 'client_webview'
      };
      expect(selectEduLoginSurface(backendConnection, null)).assertEqual(EduLoginSurface.CREDENTIALS);
      const challenge: EduPreLoginResult = {
        pre_login_token: 'token-new', captcha_required: true, captcha_type: 'image',
        captcha_image_base64: 'image', expires_at: '2026-08-25T12:00:00Z'
      };
      expect(selectEduLoginSurface(backendConnection, challenge)).assertEqual(EduLoginSurface.CAPTCHA);
      expect(selectEduLoginSurface(clientConnection, null)).assertEqual(EduLoginSurface.WEB_HANDOFF);
      expect(selectEduLoginSurface(clientConnection, challenge)).assertEqual(EduLoginSurface.WEB_HANDOFF);
    });
  });
}
