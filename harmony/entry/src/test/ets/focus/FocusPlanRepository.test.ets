import { describe, expect, it } from '@ohos/hypium';
import {
  FocusPlanMapper,
  FocusPlanProgress
} from '../../../main/ets/repository/FocusPlanRepository';
import { TaskBreakdownResponse } from '../../../main/ets/data/Models';

export default function focusPlanRepositoryTest(): void {
  describe('FocusPlanRepository', () => {
    it('maps a backend plan in step-number order and preserves policy metadata', 0, () => {
      const response: TaskBreakdownResponse = {
        mode: 'llm', goal: '复习高数', related_task_title: '高数复习', warnings: [],
        steps: [
          { step_number: 2, title: '练习', description: '完成例题', estimated_minutes: 30, dependencies: [1], completion_criteria: '完成 5 题', is_policy_step: false },
          { step_number: 1, title: '准备', description: '打开讲义', estimated_minutes: 10, dependencies: [], completion_criteria: '资料就绪', is_policy_step: true, knowledge_source: '学习指南' }
        ]
      };
      const plan = FocusPlanMapper.toPlan(response, 'task-1', '备用标题');
      expect(plan.taskTitle).assertEqual('高数复习');
      expect(plan.steps[0].stepNumber).assertEqual(1);
      expect(plan.steps[0].knowledgeSource).assertEqual('学习指南');
    });

    it('completes exactly the first pending step without changing later steps', 0, () => {
      const plan = FocusPlanMapper.toPlan({
        mode: 'rule_fallback', goal: '复习', warnings: [],
        steps: [
          { step_number: 1, title: '准备', description: '', estimated_minutes: 10, dependencies: [], completion_criteria: '完成', is_policy_step: false },
          { step_number: 2, title: '练习', description: '', estimated_minutes: 20, dependencies: [1], completion_criteria: '完成', is_policy_step: false }
        ]
      }, 'task-1', '复习');
      const updated = FocusPlanProgress.completeCurrentStep(plan);
      expect(updated.steps[0].status).assertEqual('COMPLETED');
      expect(updated.steps[1].status).assertEqual('PENDING');
      expect(FocusPlanProgress.currentStep(updated)?.stepNumber ?? 0).assertEqual(2);
    });
  });
}
