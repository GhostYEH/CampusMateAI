import { describe, expect, it } from '@ohos/hypium';
import { LostFoundItem } from '../../../main/ets/data/Models';
import { filterLostFoundFeed } from '../../../main/ets/features/lostfound/LostFoundFeed';

const ITEMS: LostFoundItem[] = [
  { id: 'lost-card', kind: 'lost', title: '校园卡', location: '图书馆', content: '黑色校园卡', created_at: '2026-08-23' },
  { id: 'found-earbuds', kind: 'found', title: '蓝牙耳机', location: '教学楼', content: '在 302 教室捡到', created_at: '2026-08-22' },
  { id: 'lost-umbrella', kind: 'lost', title: '黑色雨伞', location: '宿舍区', content: '伞柄有标签', created_at: '2026-08-21' }
];

export default function lostFoundFeedTest(): void {
  describe('LostFoundFeed', () => {
    it('shows both lost and found entries in the unified feed', 0, () => {
      const result = filterLostFoundFeed(ITEMS, 'all', '', '全部', '全部地点', true);
      expect(result.length).assertEqual(3);
      expect(result[0].id).assertEqual('lost-card');
      expect(result[1].id).assertEqual('found-earbuds');
    });

    it('applies the compact type scope without mutating the source order', 0, () => {
      const result = filterLostFoundFeed(ITEMS, 'found', '', '全部', '全部地点', false);
      expect(result.length).assertEqual(1);
      expect(result[0].id).assertEqual('found-earbuds');
      expect(ITEMS[0].id).assertEqual('lost-card');
    });

    it('combines keyword, category, and location filters', 0, () => {
      const result = filterLostFoundFeed(ITEMS, 'all', '耳机', '电子产品', '教学楼', true);
      expect(result.length).assertEqual(1);
      expect(result[0].id).assertEqual('found-earbuds');
    });
  });
}
