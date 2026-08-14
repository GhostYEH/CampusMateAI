import { describe, expect, it } from '@ohos/hypium';
import { GroupNameNormalizer } from '../../../main/ets/data/notification/GroupNameNormalizer';

export default function groupNameNormalizerTest(): void {
  describe('GroupNameNormalizer', () => {
    it('removes notification counters and normalizes full-width presentation', 0, () => {
      expect(GroupNameNormalizer.normalize('  软件工程1班（3条新消息） ')).assertEqual('软件工程1班');
      expect(GroupNameNormalizer.normalize('软件工程1班 ( 3 )')).assertEqual('软件工程1班');
    });

    it('keeps exact matching and never accepts a containing private chat title', 0, () => {
      expect(GroupNameNormalizer.matches('软件工程1班（3条新消息）', ['软件工程1班'])).assertTrue();
      expect(GroupNameNormalizer.matches('张三-软件工程1班', ['软件工程1班'])).assertFalse();
    });
  });
}
