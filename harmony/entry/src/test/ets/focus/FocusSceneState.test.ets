import { describe, expect, it } from '@ohos/hypium';
import {
  FocusDisplayMode,
  FocusSceneId,
  FocusSceneState
} from '../../../main/ets/features/focus/FocusSceneState';

export default function focusSceneStateTest(): void {
  describe('FocusSceneState', () => {
    it('defaults new focus sessions to the immersive space entry', 0, () => {
      expect(FocusSceneState.defaultDisplayMode()).assertEqual('IMMERSIVE' as FocusDisplayMode);
    });

    it('switches between immersive space and standard mode without changing the session', 0, () => {
      expect(FocusSceneState.toggleDisplayMode('IMMERSIVE')).assertEqual('STANDARD' as FocusDisplayMode);
      expect(FocusSceneState.toggleDisplayMode('STANDARD')).assertEqual('IMMERSIVE' as FocusDisplayMode);
    });

    it('keeps the three focus scenes addressable and falls back safely', 0, () => {
      expect(FocusSceneState.normalizeScene('RAINY_ROOM')).assertEqual('RAINY_ROOM' as FocusSceneId);
      expect(FocusSceneState.normalizeScene('QUIET_LIBRARY')).assertEqual('QUIET_LIBRARY' as FocusSceneId);
      expect(FocusSceneState.normalizeScene('FOREST_MORNING')).assertEqual('FOREST_MORNING' as FocusSceneId);
      expect(FocusSceneState.normalizeScene('missing')).assertEqual('RAINY_ROOM' as FocusSceneId);
      expect(FocusSceneState.assetName('FOREST_MORNING')).assertEqual('focus_scene_forest_morning.webp');
    });
  });
}
