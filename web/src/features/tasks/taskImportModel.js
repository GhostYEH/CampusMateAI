const editableFields = [
  "description", "deadline", "materials", "submission_method", "location",
  "source_name", "source_text", "priority", "importance",
];

export function selectedTaskCount(drafts) {
  return drafts.filter((draft) => draft.selected && draft.title?.trim()).length;
}

function normalizeTaskTitle(title) {
  return String(title ?? "").trim().replace(/\s+/g, " ").toLocaleLowerCase();
}

export function updateTaskImportDraftTitle(draft, title) {
  const updatedDraft = { ...draft, title };
  if (!draft.existing_task_id || normalizeTaskTitle(draft.title) === normalizeTaskTitle(title)) {
    return updatedDraft;
  }

  const { existing_task_id, existing_status, ...importableDraft } = updatedDraft;
  return { ...importableDraft, selected: true };
}

export function buildTaskImportCommit(drafts) {
  return {
    tasks: drafts
      .filter((draft) => draft.selected && draft.title?.trim())
      .map((draft) => {
        const item = { title: draft.title.trim() };
        editableFields.forEach((field) => {
          const value = draft[field];
          if (value !== undefined && value !== null && value !== "") item[field] = value;
        });
        return item;
      }),
  };
}
