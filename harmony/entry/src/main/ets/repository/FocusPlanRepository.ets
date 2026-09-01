import { FocusPlan, FocusPlanStep, TaskBreakdownResponse, TaskBreakdownStep } from '../data/Models';
import { PreferencesUtil } from '../util/PreferencesUtil';
import { StudyRepository } from './StudyRepository';

export class FocusPlanMapper {
  static toPlan(response: TaskBreakdownResponse, taskId: string, taskTitle: string): FocusPlan {
    const steps: FocusPlanStep[] = response.steps.slice().sort((left: TaskBreakdownStep, right: TaskBreakdownStep): number => left.step_number - right.step_number)
      .map((step: TaskBreakdownStep): FocusPlanStep => ({
        stepNumber: step.step_number,
        title: step.title,
        description: step.description,
        estimatedMinutes: step.estimated_minutes,
        completionCriteria: step.completion_criteria,
        dependencies: step.dependencies,
        isPolicyStep: step.is_policy_step,
        knowledgeSource: step.knowledge_source,
        status: 'PENDING'
      }));
    return {
      taskId: taskId,
      taskTitle: response.related_task_title?.trim().length ? response.related_task_title : taskTitle,
      goal: response.goal,
      steps: steps,
      updatedAtEpochMillis: Date.now()
    };
  }
}

export class FocusPlanProgress {
  static currentStep(plan: FocusPlan): FocusPlanStep | undefined {
    return plan.steps.find((step: FocusPlanStep): boolean => step.status === 'PENDING');
  }

  static completeCurrentStep(plan: FocusPlan): FocusPlan {
    const current: FocusPlanStep | undefined = FocusPlanProgress.currentStep(plan);
    if (current === undefined) return plan;
    const updatedSteps: FocusPlanStep[] = plan.steps.map((step: FocusPlanStep): FocusPlanStep => {
      if (step.stepNumber !== current.stepNumber) return step;
      return {
        stepNumber: step.stepNumber,
        title: step.title,
        description: step.description,
        estimatedMinutes: step.estimatedMinutes,
        completionCriteria: step.completionCriteria,
        dependencies: step.dependencies,
        isPolicyStep: step.isPolicyStep,
        knowledgeSource: step.knowledgeSource,
        status: 'COMPLETED'
      };
    });
    return {
      taskId: plan.taskId,
      taskTitle: plan.taskTitle,
      goal: plan.goal,
      steps: updatedSteps,
      updatedAtEpochMillis: Date.now()
    };
  }

  static isComplete(plan: FocusPlan): boolean {
    return plan.steps.length > 0 && plan.steps.every((step: FocusPlanStep): boolean => step.status === 'COMPLETED');
  }
}

export class FocusPlanRepository {
  private readonly studyRepository: StudyRepository;
  private readonly accountKey: () => string;
  private plans: Map<string, FocusPlan> = new Map<string, FocusPlan>();
  private loadedKey: string = '';

  constructor(studyRepository: StudyRepository, accountKey: () => string) {
    this.studyRepository = studyRepository;
    this.accountKey = accountKey;
  }

  async getPlan(taskId: string): Promise<FocusPlan | undefined> {
    await this.ensureLoaded();
    return this.plans.get(taskId);
  }

  async ensurePlan(taskId: string, taskTitle: string, goal: string): Promise<FocusPlan> {
    if (taskId.trim().length === 0) throw new Error('任务 ID 不能为空');
    const existing: FocusPlan | undefined = await this.getPlan(taskId);
    if (existing !== undefined) return existing;
    const response: TaskBreakdownResponse = await this.studyRepository.breakdownTask({ task_id: taskId, goal: goal.trim().length > 0 ? goal : taskTitle });
    if (response.steps.length === 0) throw new Error('任务规划没有可执行步骤');
    const plan: FocusPlan = FocusPlanMapper.toPlan(response, taskId, taskTitle);
    await this.savePlan(plan);
    return plan;
  }

  async completeCurrentStep(taskId: string): Promise<FocusPlan | undefined> {
    const plan: FocusPlan | undefined = await this.getPlan(taskId);
    if (plan === undefined) return undefined;
    const updated: FocusPlan = FocusPlanProgress.completeCurrentStep(plan);
    await this.savePlan(updated);
    return updated;
  }

  private async savePlan(plan: FocusPlan): Promise<void> {
    await this.ensureLoaded();
    this.plans.set(plan.taskId, plan);
    await PreferencesUtil.putString(this.storageKey(), JSON.stringify(Array.from(this.plans.values())));
  }

  private async ensureLoaded(): Promise<void> {
    const key: string = this.storageKey();
    if (this.loadedKey === key) return;
    const raw: string = await PreferencesUtil.getString(key, '[]');
    let restored: FocusPlan[] = [];
    try { restored = JSON.parse(raw) as FocusPlan[]; } catch (_) { restored = []; }
    this.plans = new Map<string, FocusPlan>();
    restored.forEach((plan: FocusPlan): void => { this.plans.set(plan.taskId, plan); });
    this.loadedKey = key;
  }

  private storageKey(): string {
    const normalized: string = this.accountKey().trim().slice(0, 80) || 'anonymous';
    return `focus_plans_v1_${normalized}`;
  }
}
