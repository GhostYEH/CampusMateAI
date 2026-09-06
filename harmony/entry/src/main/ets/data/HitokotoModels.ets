export interface HitokotoResponse {
  hitokoto?: string;
  from?: string;
  uuid?: string;
}

export interface HitokotoQuote {
  text: string;
  source: string;
  uuid: string;
}

export function parseHitokotoResponse(raw: string): HitokotoQuote {
  if (raw.trim().length === 0) throw new Error('一言返回空数据');
  const response: HitokotoResponse = JSON.parse(raw) as HitokotoResponse;
  const text: string = (response.hitokoto ?? '').trim();
  if (text.length === 0) throw new Error('一言响应缺少正文');
  return {
    text: text,
    source: (response.from ?? '').trim(),
    uuid: (response.uuid ?? '').trim()
  };
}

export function hitokotoDisplayText(text: string | undefined, loading: boolean): string {
  if (text !== undefined && text.trim().length > 0) return text.trim();
  return loading ? '一言加载中…' : '暂时无法获取一言';
}
