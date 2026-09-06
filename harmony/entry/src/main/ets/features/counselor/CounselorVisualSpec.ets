export class CounselorVisualSpec {
  static readonly DIGITAL_HUMAN_ORIGIN: string = 'https://appassets.campusmate';
  static readonly HERO_HEIGHT: number = 240;
  static readonly AVATAR_VIEWPORT: number = 148;
  static readonly AVATAR_IMAGE_WIDTH: number = 249;
  static readonly AVATAR_IMAGE_HEIGHT: number = 311;
  static readonly AVATAR_IMAGE_X: number = -50.5;
  static readonly AVATAR_IMAGE_Y: number = 0;

  static shouldLoadSpeechRuntime(_requestId: number, _speechText: string): boolean {
    return true;
  }

  static speechRuntimeUrl(_apiBaseUrl: string, reduceMotion: boolean = false): string {
    return `${CounselorVisualSpec.DIGITAL_HUMAN_ORIGIN}/digital-human/index.html?layout=harmony${reduceMotion ? '&reduceMotion=1' : ''}`;
  }

  static bundledResourcePath(requestUrl: string): string | null {
    const urlWithoutQuery: string = requestUrl.split('?')[0].split('#')[0];
    const prefix: string = `${CounselorVisualSpec.DIGITAL_HUMAN_ORIGIN}/`;
    if (!urlWithoutQuery.startsWith(prefix)) return null;
    const path: string = urlWithoutQuery.substring(prefix.length);
    if (path === 'digital-human/index.html' ||
      path === 'digital-human/Build/digital-human.loader.js' ||
      path === 'digital-human/Build/digital-human.framework.js' ||
      path === 'digital-human/Build/digital-human.data' ||
      path === 'digital-human/Build/digital-human.wasm') {
      return path;
    }
    return null;
  }

  static isTrustedSpeechRuntimeUrl(expectedUrl: string, candidateUrl: string): boolean {
    return candidateUrl.split('#')[0] === expectedUrl;
  }

  static shouldReportRuntimeError(expectedUrl: string, failedUrl: string, isMainFrame: boolean): boolean {
    return isMainFrame && CounselorVisualSpec.isTrustedSpeechRuntimeUrl(expectedUrl, failedUrl);
  }
}
