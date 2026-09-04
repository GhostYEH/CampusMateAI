import { describe, expect, it } from '@ohos/hypium';
import { closedTaskImportState, copyImportDraft, selectedImportTasks } from '../../../main/ets/features/tasks/TaskImportModel';
import { TaskImportDraft } from '../../../main/ets/data/Models';

export default function taskImportModelTest(): void {
  describe('TaskImportModel', () => {
    it('keeps only selected non-empty drafts', 0, () => {
      const drafts: TaskImportDraft[] = [
        { title: '已有任务', selected: false, priority: 'medium', confidence: 0.82 },
        { title: ' 课程报告 ', selected: true, priority: 'high', confidence: 0.91 }
      ];
      expect(selectedImportTasks(drafts).length).assertEqual(1);
      expect(selectedImportTasks(drafts)[0].title).assertEqual('课程报告');
    });

    it('clears the review state after a successful import', 0, () => {
      const state = closedTaskImportState();

      expect(state.open).assertFalse();
      expect(state.result).assertUndefined();
      expect(state.drafts.length).assertEqual(0);
      expect(state.error).assertEqual('');
    });

    it('clears duplicate metadata and selects a materially renamed draft', 0, () => {
      const duplicate: TaskImportDraft = {
        title: '课程报告', selected: false, priority: 'medium', confidence: 0.88,
        existing_task_id: 'task-1', existing_status: 'pending'
      };

      const renamed: TaskImportDraft = copyImportDraft(duplicate, '课程报告终稿', undefined, false);
      const whitespaceOnly: TaskImportDraft = copyImportDraft(duplicate, '  课程报告  ', undefined, false);

      expect(renamed.existing_task_id).assertUndefined();
      expect(renamed.existing_status).assertUndefined();
      expect(renamed.selected).assertTrue();
      expect(whitespaceOnly.existing_task_id).assertEqual('task-1');
      expect(whitespaceOnly.existing_status).assertEqual('pending');
      expect(whitespaceOnly.selected).assertFalse();
    });
  });
}
