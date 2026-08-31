export class CounselorVisualSpec {
  static readonly HERO_HEIGHT: number = 240;
  static readonly AVATAR_VIEWPORT: number = 148;
  static readonly AVATAR_IMAGE_WIDTH: number = 249;
  static readonly AVATAR_IMAGE_HEIGHT: number = 311;
  static readonly AVATAR_IMAGE_X: number = -50.5;
  static readonly AVATAR_IMAGE_Y: number = 0;

  static shouldLoadSpeechRuntime(_requestId: number, _speechText: string): boolean {
    return true;
  }

  static speechRuntimeUrl(apiBaseUrl: string, reduceMotion: boolean = false): string {
    const normalized: string = apiBaseUrl.replace(/\/+$/, '').replace(/\/api\/v1$/, '');
    return `${normalized}/digital-human/mobile.html?layout=harmony&fallback=1${reduceMotion ? '&reduceMotion=1' : ''}`;
  }

  static isTrustedSpeechRuntimeUrl(expectedUrl: string, candidateUrl: string): boolean {
    return candidateUrl.split('#')[0] === expectedUrl;
  }
}
