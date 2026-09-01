import { TaskImportAnalyzeResponse, TaskImportDraft } from '../../data/Models';

export interface TaskImportClosedState {
  open: boolean;
  result?: TaskImportAnalyzeResponse;
  drafts: TaskImportDraft[];
  error: string;
}

export function closedTaskImportState(): TaskImportClosedState {
  return { open: false, result: undefined, drafts: [], error: '' };
}

export function selectedImportTasks(drafts: TaskImportDraft[]): TaskImportDraft[] {
  return drafts
    .filter((draft: TaskImportDraft) => draft.selected && draft.title.trim().length > 0)
    .map((draft: TaskImportDraft): TaskImportDraft => copyImportDraft(draft, draft.title.trim(), draft.description, draft.selected));
}

export function copyImportDraft(draft: TaskImportDraft, title: string, description: string | undefined, selected: boolean): TaskImportDraft {
  const renamed: boolean = draft.existing_task_id !== undefined && normalizeImportTitle(title) !== normalizeImportTitle(draft.title);
  return {
    title: title,
    description: description,
    deadline: draft.deadline,
    source_name: draft.source_name,
    source_text: draft.source_text,
    priority: draft.priority,
    importance: draft.importance,
    confidence: draft.confidence,
    selected: renamed ? true : selected,
    existing_task_id: renamed ? undefined : draft.existing_task_id,
    existing_status: renamed ? undefined : draft.existing_status
  };
}

function normalizeImportTitle(title: string): string {
  return title.trim().toLowerCase();
}
