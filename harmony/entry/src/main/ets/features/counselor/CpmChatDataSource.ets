export enum CpmMessageStatus {
  GENERATING = 'GENERATING',
  COMPLETED = 'COMPLETED',
  ERROR = 'ERROR'
}

export type CpmMessageRole = 'user' | 'assistant';

@Observed
export class CpmChatMessage {
  id: string;
  role: CpmMessageRole;
  content: string;
  status: CpmMessageStatus;
  errorMessage: string;

  constructor(id: string, role: CpmMessageRole, content: string, status: CpmMessageStatus, errorMessage: string = '') {
    this.id = id;
    this.role = role;
    this.content = content;
    this.status = status;
    this.errorMessage = errorMessage;
  }
}

export class CpmChatDataSource implements IDataSource {
  private messages: CpmChatMessage[] = [];
  private listeners: DataChangeListener[] = [];
  onChanged: () => void = () => {};

  totalCount(): number {
    return this.messages.length;
  }

  getData(index: number): CpmChatMessage {
    return this.messages[index];
  }

  registerDataChangeListener(listener: DataChangeListener): void {
    if (this.listeners.indexOf(listener) < 0) this.listeners.push(listener);
  }

  unregisterDataChangeListener(listener: DataChangeListener): void {
    const index = this.listeners.indexOf(listener);
    if (index >= 0) this.listeners.splice(index, 1);
  }

  addUserAndAssistant(question: string, now: number): string {
    const assistantId = `assistant-${now}`;
    this.push(new CpmChatMessage(`user-${now}`, 'user', question, CpmMessageStatus.COMPLETED));
    this.push(new CpmChatMessage(assistantId, 'assistant', '', CpmMessageStatus.GENERATING));
    return assistantId;
  }

  appendChunk(id: string, chunk: string): void {
    const index = this.findIndex(id);
    if (index < 0 || chunk.length === 0) return;
    this.messages[index].content += chunk;
    this.notifyChange(index);
  }

  complete(id: string, fallbackAnswer: string = ''): string {
    const index = this.findIndex(id);
    if (index < 0) return '';
    if (this.messages[index].content.length === 0 && fallbackAnswer.length > 0) {
      this.messages[index].content = fallbackAnswer;
    }
    this.messages[index].status = CpmMessageStatus.COMPLETED;
    this.notifyChange(index);
    return this.messages[index].content;
  }

  fail(id: string, error: string): void {
    const index = this.findIndex(id);
    if (index < 0) return;
    if (this.messages[index].content.length === 0) this.messages[index].content = '暂时无法生成回答，请稍后重试。';
    this.messages[index].status = CpmMessageStatus.ERROR;
    this.messages[index].errorMessage = error;
    this.notifyChange(index);
  }

  findLastUserPrompt(): string {
    for (let index = this.messages.length - 1; index >= 0; index--) {
      if (this.messages[index].role === 'user') return this.messages[index].content;
    }
    return '';
  }

  private findIndex(id: string): number {
    return this.messages.findIndex((message: CpmChatMessage) => message.id === id);
  }

  private push(message: CpmChatMessage): void {
    this.messages.push(message);
    const index = this.messages.length - 1;
    this.listeners.forEach((listener: DataChangeListener) => listener.onDataAdd(index));
    this.onChanged();
  }

  private notifyChange(index: number): void {
    this.listeners.forEach((listener: DataChangeListener) => listener.onDataChange(index));
    this.onChanged();
  }
}
