import { LostFoundItem } from '../../data/Models';

export type LostFoundFeedScope = 'all' | 'lost' | 'found';

function itemText(item: LostFoundItem): string {
  return `${item.title ?? ''} ${item.content ?? ''} ${item.location ?? ''}`.toLowerCase();
}

export function lostFoundCategoryForItem(item: LostFoundItem): string {
  const text: string = itemText(item);
  if (text.includes('校园卡') || text.includes('学生证') || text.includes('身份证') || text.includes('银行卡') || text.includes('证件')) return '证件卡片';
  if (text.includes('耳机') || text.includes('手机') || text.includes('充电') || text.includes('电脑') || text.includes('平板') || text.includes('电子')) return '电子产品';
  if (text.includes('书') || text.includes('资料') || text.includes('笔记')) return '书籍资料';
  if (text.includes('钥匙') || text.includes('雨伞') || text.includes('水杯') || text.includes('衣') || text.includes('生活')) return '生活用品';
  return '其他';
}

export function filterLostFoundFeed(
  items: LostFoundItem[],
  scope: LostFoundFeedScope,
  query: string,
  category: string,
  location: string,
  newestFirst: boolean
): LostFoundItem[] {
  const normalizedQuery: string = query.trim().toLowerCase();
  const result: LostFoundItem[] = items.filter((item: LostFoundItem): boolean => {
    const inScope: boolean = scope === 'all' || item.kind === scope;
    const matchesQuery: boolean = normalizedQuery.length === 0 || itemText(item).includes(normalizedQuery);
    const matchesCategory: boolean = category === '全部' || lostFoundCategoryForItem(item) === category;
    const matchesLocation: boolean = location === '全部地点' || (item.location ?? '').includes(location);
    return inScope && matchesQuery && matchesCategory && matchesLocation;
  });
  return newestFirst ? result : result.slice().reverse();
}
