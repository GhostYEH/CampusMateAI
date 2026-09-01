import { http } from '@kit.NetworkKit';
import { ApiClient } from '../data/ApiClient';
import { FocusAiAskRequest, FocusAiAskResponse } from '../data/Models';

export class FocusAiRepository {
  private readonly client: ApiClient;

  constructor(client: ApiClient) {
    this.client = client;
  }

  async ask(text: string): Promise<string> {
    const normalized: string = text.trim();
    if (normalized.length === 0) throw new Error('请输入要询问的内容');
    const request: FocusAiAskRequest = { text: normalized };
    const response: FocusAiAskResponse = await this.client.request<FocusAiAskResponse>(http.RequestMethod.POST, 'focus/ai/ask', request);
    if (response.answer.trim().length === 0) throw new Error('AI 未返回有效回答');
    return response.answer;
  }
}
