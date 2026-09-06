import { describe, expect, it } from '@ohos/hypium';
import { hitokotoDisplayText, parseHitokotoResponse } from '../../../main/ets/data/HitokotoModels';

export default function hitokotoModelsTest(): void {
  describe('HitokotoModels', () => {
    it('parses the sentence and source from the public response shape', 0, () => {
      const quote = parseHitokotoResponse('{"hitokoto":"写下想说的话。","from":"原创","uuid":"quote-1"}');

      expect(quote.text).assertEqual('写下想说的话。');
      expect(quote.source).assertEqual('原创');
      expect(quote.uuid).assertEqual('quote-1');
    });

    it('uses a quiet fallback instead of the removed sparkle copy', 0, () => {
      const text = hitokotoDisplayText(undefined, false);

      expect(text).assertEqual('暂时无法获取一言');
      expect(text.includes('闪闪发光')).assertFalse();
    });
  });
}
