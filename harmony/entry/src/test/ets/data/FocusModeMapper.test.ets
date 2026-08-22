import { describe, expect, it } from '@ohos/hypium';
import { FocusModeMapper } from '../../../main/ets/data/FocusModeMapper';
import { FocusMode } from '../../../main/ets/data/Models';

export default function focusModeMapperTest(): void {
  describe('FocusModeMapper', () => {
    it('maps Chinese labels to FocusMode enum values', 0, () => {
      expect(FocusModeMapper.fromLabel('专注')).assertEqual('focus');
      expect(FocusModeMapper.fromLabel('短休息')).assertEqual('short_break');
      expect(FocusModeMapper.fromLabel('长休息')).assertEqual('long_break');
    });

    it('falls back to focus for unknown labels', 0, () => {
      expect(FocusModeMapper.fromLabel('')).assertEqual('focus');
      expect(FocusModeMapper.fromLabel('未知')).assertEqual('focus');
    });

    it('round-trips label and mode without loss', 0, () => {
      const modes: FocusMode[] = ['focus', 'short_break', 'long_break'];
      modes.forEach((mode: FocusMode) => {
        expect(FocusModeMapper.fromLabel(FocusModeMapper.toLabel(mode))).assertEqual(mode);
      });
    });
  });
}