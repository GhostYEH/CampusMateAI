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

    it('keeps the expensive speech runtime off the initial screen', 0, () => {
      expect(CounselorVisualSpec.shouldLoadSpeechRuntime(0, '')).assertFalse();
      expect(CounselorVisualSpec.shouldLoadSpeechRuntime(1, '')).assertFalse();
      expect(CounselorVisualSpec.shouldLoadSpeechRuntime(1, '你好')).assertTrue();
    });

    it('uses the lightweight Harmony fallback runtime when speech is requested', 0, () => {
      expect(CounselorVisualSpec.speechRuntimeUrl('http://127.0.0.1:8000/api/v1'))
        .assertEqual('http://127.0.0.1:8000/digital-human/mobile.html?layout=harmony&fallback=1');
    });
  });
}
