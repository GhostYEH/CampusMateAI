export interface EduLoginSensitiveState {
  username: string;
  password: string;
  captcha: string;
  preLoginToken?: string;
}

export enum EduLoginSensitiveEvent {
  DIRECT_CONNECTED,
  WEB_HANDOFF,
  DISCONNECT,
  CONNECTION_REPLACED,
  CANCEL,
  DISPOSE
}

export function captureEduLoginChallenge(
  state: EduLoginSensitiveState,
  captcha: string,
  preLoginToken: string
): EduLoginSensitiveState {
  return {
    username: state.username,
    password: state.password,
    captcha: captcha,
    preLoginToken: preLoginToken
  };
}

export function reduceEduLoginSensitiveState(
  state: EduLoginSensitiveState,
  event: EduLoginSensitiveEvent
): EduLoginSensitiveState {
  return {
    username: state.username,
    password: '',
    captcha: '',
    preLoginToken: undefined
  };
}
