import { describe, expect, it } from '@ohos/hypium';
import {
  EduBindingDto,
  EduConnectionDto,
  EduPreLoginResult,
  EduSyncResult
} from '../../../main/ets/data/ApiClient';
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
  EduConnectionRequestToken,
  EduPostConnectRequestToken
} from '../../../main/ets/features/edu/EduConnectionRequestGuard';
import {
  EduLoginSurface,
  selectEduLoginSurface
} from '../../../main/ets/features/edu/EduLoginSurface';
import {
  EduPostConnectController,
  EduPostConnectOperations,
  EduPostConnectStateWriter,
  invalidateEduConnectionLifecycle
} from '../../../main/ets/features/edu/EduPostConnectController';

class Deferred<T> {
  promise: Promise<T>;
  private resolvePromise: (value: T) => void = (_value: T): void => {};

  constructor() {
    this.promise = new Promise<T>((resolve: (value: T) => void): void => {
      this.resolvePromise = resolve;
    });
  }

  resolve(value: T): void {
    this.resolvePromise(value);
  }
}

class PostConnectState implements EduPostConnectStateWriter {
  binding: EduBindingDto | null = null;
  syncing: boolean = false;
  syncMessage: string = '';
  connectionId: string | undefined = undefined;
  password: string = '';
  captcha: string = '';
  preLoginToken: string | undefined = undefined;

  setBinding(binding: EduBindingDto | null): void {
    this.binding = binding;
  }

  setSyncing(syncing: boolean): void {
    this.syncing = syncing;
  }

  setSyncMessage(message: string): void {
    this.syncMessage = message;
  }

  clearForLifecycleExit(): void {
    this.binding = null;
    this.syncing = false;
    this.syncMessage = '';
    this.connectionId = undefined;
    this.password = '';
    this.captcha = '';
    this.preLoginToken = undefined;
  }
}

class DelayedPostConnectOperations implements EduPostConnectOperations {
  bindingResult: Promise<EduBindingDto | undefined>;
  scheduleResult: Promise<EduSyncResult>;
  gradeResult: Promise<EduSyncResult>;

  constructor(
    bindingResult: Promise<EduBindingDto | undefined>,
    scheduleResult: Promise<EduSyncResult>,
    gradeResult: Promise<EduSyncResult>
  ) {
    this.bindingResult = bindingResult;
    this.scheduleResult = scheduleResult;
    this.gradeResult = gradeResult;
  }

  getBinding(): Promise<EduBindingDto | undefined> {
    return this.bindingResult;
  }

  syncSchedule(): Promise<EduSyncResult> {
    return this.scheduleResult;
  }

  syncGrade(): Promise<EduSyncResult> {
    return this.gradeResult;
  }
}

function bindingFixture(id: string): EduBindingDto {
  return {
    id: id,
    user_id: 'user-1',
    university_id: 'university-1',
    provider: 'zhengfang',
    system_type: 'zhengfang',
    connection_status: 'active'
  };
}

function syncFixture(type: string): EduSyncResult {
  return { sync_type: type, status: 'success', items_count: 1 };
}

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

    it('drops a delayed onConnected binding after connection replacement', 0, async () => {
      const guard: EduConnectionRequestGuard = new EduConnectionRequestGuard();
      const oldGeneration: number = guard.beginReplacement();
      expect(guard.acceptCreatedConnection(oldGeneration, 'connection-old')).assertTrue();
      const oldRequest: EduPostConnectRequestToken | undefined = guard.capturePostConnect('connection-old');
      expect(oldRequest !== undefined).assertTrue();
      const delayedBinding: Deferred<EduBindingDto | undefined> = new Deferred<EduBindingDto | undefined>();
      const state: PostConnectState = new PostConnectState();
      state.connectionId = 'connection-old';
      state.password = 'old-secret';
      state.captcha = '1234';
      state.preLoginToken = 'old-token';
      const operations: DelayedPostConnectOperations = new DelayedPostConnectOperations(
        delayedBinding.promise,
        Promise.resolve(syncFixture('schedule')),
        Promise.resolve(syncFixture('grade'))
      );
      const controller: EduPostConnectController = new EduPostConnectController(guard, operations, state);
      const oldTask: Promise<void> = controller.onConnected(oldRequest as EduPostConnectRequestToken);
      await Promise.resolve();

      const newGeneration: number = invalidateEduConnectionLifecycle(
        guard,
        (): void => {},
        (): void => state.clearForLifecycleExit()
      );
      expect(guard.acceptCreatedConnection(newGeneration, 'connection-new')).assertTrue();
      state.connectionId = 'connection-new';
      delayedBinding.resolve(bindingFixture('binding-old'));
      await oldTask;

      expect(state.binding === null).assertTrue();
      expect(state.syncMessage).assertEqual('');
      expect(state.syncing).assertFalse();
      expect(state.connectionId).assertEqual('connection-new');
      expect(state.password).assertEqual('');
      expect(state.captcha).assertEqual('');
      expect(state.preLoginToken === undefined).assertTrue();
    });

    it('does not let an old sync finally stop the replacement sync spinner', 0, async () => {
      const guard: EduConnectionRequestGuard = new EduConnectionRequestGuard();
      const oldGeneration: number = guard.beginReplacement();
      expect(guard.acceptCreatedConnection(oldGeneration, 'connection-old')).assertTrue();
      const oldRequest: EduPostConnectRequestToken | undefined = guard.capturePostConnect('connection-old');
      expect(oldRequest !== undefined).assertTrue();
      const oldSchedule: Deferred<EduSyncResult> = new Deferred<EduSyncResult>();
      const state: PostConnectState = new PostConnectState();
      state.connectionId = 'connection-old';
      const oldOperations: DelayedPostConnectOperations = new DelayedPostConnectOperations(
        Promise.resolve(bindingFixture('binding-old')),
        oldSchedule.promise,
        Promise.resolve(syncFixture('grade'))
      );
      const oldController: EduPostConnectController = new EduPostConnectController(guard, oldOperations, state);
      const oldTask: Promise<void> = oldController.autoSync(oldRequest as EduPostConnectRequestToken);
      await Promise.resolve();
      expect(state.syncing).assertTrue();

      const newGeneration: number = invalidateEduConnectionLifecycle(
        guard,
        (): void => {},
        (): void => state.clearForLifecycleExit()
      );
      expect(guard.acceptCreatedConnection(newGeneration, 'connection-new')).assertTrue();
      state.connectionId = 'connection-new';
      const newRequest: EduPostConnectRequestToken | undefined = guard.capturePostConnect('connection-new');
      expect(newRequest !== undefined).assertTrue();
      const newSchedule: Deferred<EduSyncResult> = new Deferred<EduSyncResult>();
      const newOperations: DelayedPostConnectOperations = new DelayedPostConnectOperations(
        Promise.resolve(bindingFixture('binding-new')),
        newSchedule.promise,
        Promise.resolve(syncFixture('grade'))
      );
      const newController: EduPostConnectController = new EduPostConnectController(guard, newOperations, state);
      const newTask: Promise<void> = newController.autoSync(newRequest as EduPostConnectRequestToken);
      await Promise.resolve();

      oldSchedule.resolve(syncFixture('schedule'));
      await oldTask;
      expect(state.syncing).assertTrue();
      expect(state.syncMessage).assertEqual('正在同步课表…');
      expect(state.connectionId).assertEqual('connection-new');

      newSchedule.resolve(syncFixture('schedule'));
      await newTask;
      expect(state.syncing).assertFalse();
      expect(state.binding?.id).assertEqual('binding-new');
    });

    it('drops a delayed grade result after dispose clears connection and secrets', 0, async () => {
      const guard: EduConnectionRequestGuard = new EduConnectionRequestGuard();
      const generation: number = guard.beginReplacement();
      expect(guard.acceptCreatedConnection(generation, 'connection-old')).assertTrue();
      const request: EduPostConnectRequestToken | undefined = guard.capturePostConnect('connection-old');
      expect(request !== undefined).assertTrue();
      const delayedGrade: Deferred<EduSyncResult> = new Deferred<EduSyncResult>();
      const state: PostConnectState = new PostConnectState();
      state.connectionId = 'connection-old';
      state.password = 'old-secret';
      state.captcha = '5678';
      state.preLoginToken = 'old-token';
      const operations: DelayedPostConnectOperations = new DelayedPostConnectOperations(
        Promise.resolve(bindingFixture('binding-old')),
        Promise.resolve(syncFixture('schedule')),
        delayedGrade.promise
      );
      const controller: EduPostConnectController = new EduPostConnectController(guard, operations, state);
      const oldTask: Promise<void> = controller.autoSync(request as EduPostConnectRequestToken);
      await Promise.resolve();
      await Promise.resolve();
      expect(state.syncMessage).assertEqual('正在同步成绩…');

      invalidateEduConnectionLifecycle(
        guard,
        (): void => {},
        (): void => state.clearForLifecycleExit()
      );
      delayedGrade.resolve(syncFixture('grade'));
      await oldTask;

      expect(state.binding === null).assertTrue();
      expect(state.syncMessage).assertEqual('');
      expect(state.syncing).assertFalse();
      expect(state.connectionId === undefined).assertTrue();
      expect(state.password).assertEqual('');
      expect(state.captcha).assertEqual('');
      expect(state.preLoginToken === undefined).assertTrue();
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
