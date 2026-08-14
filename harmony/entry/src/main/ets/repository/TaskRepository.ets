import { http } from '@kit.NetworkKit';
import { ApiClient } from '../data/ApiClient';
import { PagedResponse, TaskItem } from '../data/Models';

export interface TaskUpdateRequest {
  title: string;
  description?: string;
  deadline?: string;
  source_name?: string;
}

export class TaskRepository {
  private readonly client: ApiClient;

  constructor(client: ApiClient) { this.client = client; }

  async list(): Promise<TaskItem[]> {
    const page = await this.client.request<PagedResponse<TaskItem>>(http.RequestMethod.GET, 'tasks?page=1&page_size=100');
    return page.items ?? [];
  }

  async update(id: string, request: TaskUpdateRequest): Promise<TaskItem> {
    return this.client.patch<TaskItem>(`tasks/${id}`, request);
  }

  async delete(id: string): Promise<void> {
    await this.client.requestVoid(http.RequestMethod.DELETE, `tasks/${id}`);
  }

  async setCompleted(task: TaskItem): Promise<void> {
    const action = task.status === 'completed' ? 'restore' : 'complete';
    await this.client.requestVoid(http.RequestMethod.POST, `tasks/${task.id}/${action}`);
  }
}
