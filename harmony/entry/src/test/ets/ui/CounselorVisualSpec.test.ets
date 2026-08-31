import { describe, expect, it } from '@ohos/hypium';
import { CounselorVisualSpec } from '../../../main/ets/features/counselor/CounselorVisualSpec';

export default function counselorVisualSpecTest(): void {
  describe('CounselorVisualSpec', () => {
    it('matches the target hero geometry and top-centered avatar crop', 0, () => {
      expect(CounselorVisualSpec.HERO_HEIGHT).assertEqual(240);
      expect(CounselorVisualSpec.AVATAR_VIEWPORT).assertEqual(148);
      expect(CounselorVisualSpec.AVATAR_IMAGE_WIDTH).assertEqual(249);
      expect(CounselorVisualSpec.AVATAR_IMAGE_HEIGHT).assertEqual(311);
      expect(CounselorVisualSpec.AVATAR_IMAGE_X).assertEqual(-50.5);
      expect(CounselorVisualSpec.AVATAR_IMAGE_Y).assertEqual(0);
    });

    it('loads the lightweight avatar runtime immediately for idle motion', 0, () => {
      expect(CounselorVisualSpec.shouldLoadSpeechRuntime(0, '')).assertTrue();
      expect(CounselorVisualSpec.shouldLoadSpeechRuntime(1, '')).assertTrue();
      expect(CounselorVisualSpec.shouldLoadSpeechRuntime(1, '你好')).assertTrue();
    });

    it('uses the lightweight Harmony fallback runtime when speech is requested', 0, () => {
      expect(CounselorVisualSpec.speechRuntimeUrl('http://127.0.0.1:8000/api/v1'))
        .assertEqual('http://127.0.0.1:8000/digital-human/mobile.html?layout=harmony&fallback=1');
      expect(CounselorVisualSpec.speechRuntimeUrl('http://127.0.0.1:8000/api/v1', true))
        .assertEqual('http://127.0.0.1:8000/digital-human/mobile.html?layout=harmony&fallback=1&reduceMotion=1');
    });

    it('only trusts the exact digital human runtime document', 0, () => {
      const expected: string = 'https://campus.example/digital-human/mobile.html?layout=harmony&fallback=1';
      expect(CounselorVisualSpec.isTrustedSpeechRuntimeUrl(expected, expected)).assertTrue();
      expect(CounselorVisualSpec.isTrustedSpeechRuntimeUrl(expected, `${expected}#avatar`)).assertTrue();
      expect(CounselorVisualSpec.isTrustedSpeechRuntimeUrl(
        expected,
        'https://evil.example/digital-human/mobile.html?layout=harmony&fallback=1',
      )).assertFalse();
      expect(CounselorVisualSpec.isTrustedSpeechRuntimeUrl(
        expected,
        'https://campus.example/other.html?layout=harmony&fallback=1',
      )).assertFalse();
      expect(CounselorVisualSpec.isTrustedSpeechRuntimeUrl(
        expected,
        'https://campus.example/digital-human/mobile.html?layout=harmony',
      )).assertFalse();
    });
  });
}
