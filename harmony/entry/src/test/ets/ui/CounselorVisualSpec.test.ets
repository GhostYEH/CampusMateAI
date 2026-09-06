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

    it('uses the HAP bundled Rusk runtime without depending on the API host', 0, () => {
      expect(CounselorVisualSpec.speechRuntimeUrl('http://127.0.0.1:8000/api/v1'))
        .assertEqual('https://appassets.campusmate/digital-human/index.html?layout=harmony');
      expect(CounselorVisualSpec.speechRuntimeUrl('http://127.0.0.1:8000/api/v1', true))
        .assertEqual('https://appassets.campusmate/digital-human/index.html?layout=harmony&reduceMotion=1');
    });

    it('maps only known appasset URLs to bundled Unity resources', 0, () => {
      expect(CounselorVisualSpec.bundledResourcePath(
        'https://appassets.campusmate/digital-human/index.html?layout=harmony',
      )).assertEqual('digital-human/index.html');
      expect(CounselorVisualSpec.bundledResourcePath(
        'https://appassets.campusmate/digital-human/Build/digital-human.wasm',
      )).assertEqual('digital-human/Build/digital-human.wasm');
      expect(CounselorVisualSpec.bundledResourcePath(
        'https://evil.example/digital-human/Build/digital-human.wasm',
      )).assertNull();
      expect(CounselorVisualSpec.bundledResourcePath(
        'https://appassets.campusmate/digital-human/Build/unknown.bin',
      )).assertNull();
    });

    it('only trusts the exact digital human runtime document', 0, () => {
      const expected: string = 'https://appassets.campusmate/digital-human/index.html?layout=harmony';
      expect(CounselorVisualSpec.isTrustedSpeechRuntimeUrl(expected, expected)).assertTrue();
      expect(CounselorVisualSpec.isTrustedSpeechRuntimeUrl(expected, `${expected}#avatar`)).assertTrue();
      expect(CounselorVisualSpec.isTrustedSpeechRuntimeUrl(
        expected,
        'https://evil.example/digital-human/index.html?layout=harmony',
      )).assertFalse();
      expect(CounselorVisualSpec.isTrustedSpeechRuntimeUrl(
        expected,
        'https://appassets.campusmate/other.html?layout=harmony',
      )).assertFalse();
      expect(CounselorVisualSpec.isTrustedSpeechRuntimeUrl(
        expected,
        'https://appassets.campusmate/digital-human/index.html?layout=harmony&fallback=1',
      )).assertFalse();
    });

    it('does not turn optional subresource failures into a runtime failure', 0, () => {
      const expected: string = 'https://appassets.campusmate/digital-human/index.html?layout=harmony';
      expect(CounselorVisualSpec.shouldReportRuntimeError(expected, expected, true)).assertTrue();
      expect(CounselorVisualSpec.shouldReportRuntimeError(
        expected,
        'https://appassets.campusmate/digital-human/Build/digital-human.data',
        false,
      )).assertFalse();
      expect(CounselorVisualSpec.shouldReportRuntimeError(
        expected,
        'https://unavailable.example/optional-resource',
        false,
      )).assertFalse();
    });
  });
}
