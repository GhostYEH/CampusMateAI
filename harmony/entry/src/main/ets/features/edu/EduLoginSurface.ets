import { EduConnectionDto, EduPreLoginResult } from '../../data/ApiClient';

export enum EduLoginSurface {
  NONE,
  CREDENTIALS,
  CAPTCHA,
  WEB_HANDOFF
}

/** Selects one mutually exclusive login action surface for the current production state. */
export function selectEduLoginSurface(
  connection: EduConnectionDto | null,
  preLoginResult: EduPreLoginResult | null
): EduLoginSurface {
  if (connection === null) return EduLoginSurface.NONE;
  if (connection.login_execution_mode === 'client_webview') return EduLoginSurface.WEB_HANDOFF;
  if (connection.login_execution_mode !== 'backend_http') return EduLoginSurface.NONE;
  return preLoginResult === null ? EduLoginSurface.CREDENTIALS : EduLoginSurface.CAPTCHA;
}
