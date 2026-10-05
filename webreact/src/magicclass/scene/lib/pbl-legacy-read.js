import { isRunnablePBLProjectV2 } from './pbl-types-guards.js';

/**
 * 移植自参考项目 `lib/pbl/legacy/read.ts`。
 * 仅擦除 TypeScript 类型标注（interface / type / 泛型 / `as`），逻辑逐字保留。
 *
 * Read-only support for PBL v1 scenes stored before the v2 cutover.
 *
 * This module is kept indefinitely so historical scenes remain renderable and
 * exportable. Writers must never import it to create or project legacy shapes;
 * v1 data is accepted only when it already exists in stored scene content.
 */

const LEGACY_INSTRUCTOR_ROLE_ID = 'role-compat-instructor';

export function upgradeLegacyPBLConfigToProjectV2(config) {
  const now = new Date().toISOString();
  const language = detectLegacyLanguage(config);
  const instructorRole = {
    id: LEGACY_INSTRUCTOR_ROLE_ID,
    type: 'instructor',
    name: inferInstructorName(config),
    description: 'Guides the learner through the upgraded legacy PBL project.',
  };
  const orderedIssues = config.issueboard.issues.slice().sort((a, b) => a.index - b.index);
  const activeIssueId = inferActiveIssueId(config);
  const allDone = orderedIssues.length > 0 && orderedIssues.every((issue) => issue.is_done);
  const hasLegacyRuntime =
    !!config.selectedRole ||
    config.chat.messages.length > 0 ||
    orderedIssues.some((issue) => issue.is_done);

  return {
    uiPhase: allDone ? 'completed' : hasLegacyRuntime ? 'workspace' : 'hero',
    title: config.projectInfo.title || 'Project',
    description: config.projectInfo.description || '',
    proficiency: '',
    language,
    tags: [],
    status: allDone ? 'completed' : 'active',
    roles: [instructorRole],
    milestones: orderedIssues.map((issue, index) => {
      const status = legacyIssueStatus(issue, index, orderedIssues, activeIssueId);
      return {
        id: `legacy_ms_${issue.id}`,
        title: issue.title || `Task ${index + 1}`,
        description: issue.description || issue.notes || undefined,
        status,
        order: index,
        microtasks: [
          {
            id: `legacy_mt_${issue.id}`,
            title: issue.title || `Task ${index + 1}`,
            description: legacyMicrotaskDescription(issue),
            status:
              status === 'completed' ? 'completed' : status === 'active' ? 'in_progress' : 'todo',
            assignee: 'user',
            hints: issue.generated_questions ? [issue.generated_questions] : [],
            order: 0,
          },
        ],
        documents: issue.notes
          ? [
              {
                id: `doc_${issue.id}`,
                title: 'Legacy issue notes',
                content: issue.notes,
                docType: 'reference',
              },
            ]
          : [],
        briefing: issue.generated_questions || issue.description || issue.title,
        completionCriteria: legacyCompletionCriteria(language),
        debrief: legacyDebrief(language),
      };
    }),
    submissions: [],
    evaluations: [],
    threads: [
      {
        agentId: instructorRole.id,
        messages: config.chat.messages
          .filter((message) => typeof message.message === 'string')
          .map((message) => legacyChatMessage(message, config)),
      },
    ],
    engagementEvents: [],
    createdAt: now,
    updatedAt: now,
  };
}

export function isEmptyLegacyPBLConfig(config) {
  if (
    !config ||
    Array.isArray(config) ||
    typeof config !== 'object' ||
    !config?.projectInfo ||
    Array.isArray(config.projectInfo) ||
    typeof config.projectInfo !== 'object' ||
    !Array.isArray(config?.agents) ||
    config.agents.some(
      (agent) =>
        !agent ||
        Array.isArray(agent) ||
        typeof agent !== 'object' ||
        (agent.name !== undefined && agent.name !== null && typeof agent.name !== 'string'),
    ) ||
    !config?.issueboard ||
    Array.isArray(config.issueboard) ||
    typeof config.issueboard !== 'object' ||
    !Array.isArray(config.issueboard?.issues) ||
    config.issueboard.issues.some(
      (issue) => !issue || Array.isArray(issue) || typeof issue !== 'object',
    ) ||
    !config?.chat ||
    Array.isArray(config.chat) ||
    typeof config.chat !== 'object' ||
    !Array.isArray(config.chat?.messages) ||
    config.chat.messages.some(
      (message) => !message || Array.isArray(message) || typeof message !== 'object',
    ) ||
    (config.selectedRole !== undefined &&
      config.selectedRole !== null &&
      typeof config.selectedRole !== 'string')
  ) {
    return true;
  }
  return (
    !config?.projectInfo?.title &&
    !config?.projectInfo?.description &&
    config.agents.length === 0 &&
    config.issueboard.issues.length === 0 &&
    config.chat.messages.length === 0
  );
}

export function resolvePBLContent(content) {
  if (isRunnablePBLProjectV2(content.projectV2)) {
    return { kind: 'v2', projectV2: content.projectV2 };
  }

  if (
    content.projectConfig != null &&
    !isEmptyLegacyPBLConfig(content.projectConfig) &&
    content.projectConfig.issueboard.issues.length > 0
  ) {
    return { kind: 'legacy', projectConfig: content.projectConfig };
  }

  return { kind: 'empty' };
}

export function normalizeLegacyPBLContent(content) {
  const resolved = resolvePBLContent(content);
  if (resolved.kind === 'legacy') {
    return {
      type: 'pbl',
      projectV2: upgradeLegacyPBLConfigToProjectV2(resolved.projectConfig),
    };
  }

  return content;
}

function legacyIssueStatus(issue, index, issues, activeIssueId) {
  if (issue.is_done) return 'completed';
  if (issue.id === activeIssueId) return 'active';

  const firstIncomplete = issues.find((candidate) => !candidate.is_done);
  if (!activeIssueId && (firstIncomplete ? issue.id === firstIncomplete.id : index === 0)) {
    return 'active';
  }
  return 'locked';
}

function legacyMicrotaskDescription(issue) {
  return [issue.description, issue.notes ? `Notes: ${issue.notes}` : ''].filter(Boolean).join('\n');
}

function legacyChatMessage(message, config) {
  const isUser = isLegacyUserMessage(message, config);
  const timestamp = new Date(message.timestamp || Date.now());
  return {
    id: message.id,
    agentId: isUser ? undefined : LEGACY_INSTRUCTOR_ROLE_ID,
    roleType: isUser ? 'user' : 'instructor',
    content: message.message,
    ts: Number.isNaN(timestamp.getTime()) ? new Date().toISOString() : timestamp.toISOString(),
  };
}

function isLegacyUserMessage(message, config) {
  const selectedRole =
    config.selectedRole?.trim() || config.agents.find((agent) => agent.is_user_role)?.name?.trim();
  if (selectedRole) return message.agent_name === selectedRole;
  const agentNames = new Set(config.agents.map((agent) => agent.name));
  return !agentNames.has(message.agent_name);
}

function inferInstructorName(config) {
  const activeIssue =
    config.issueboard.issues.find((issue) => issue.is_active && !issue.is_done) ??
    config.issueboard.issues.find(
      (issue) => issue.id === config.issueboard.current_issue_id && !issue.is_done,
    );
  if (activeIssue?.question_agent_name) return activeIssue.question_agent_name;
  const questionAgent = config.agents.find((agent) =>
    agent.name?.toLowerCase().includes('question'),
  );
  return questionAgent?.name || 'Instructor';
}

function inferActiveIssueId(config) {
  const issues = config.issueboard.issues;
  return (
    issues.find((issue) => issue.is_active && !issue.is_done)?.id ??
    issues.find((issue) => issue.id === config.issueboard.current_issue_id && !issue.is_done)?.id ??
    null
  );
}

function detectLegacyLanguage(config) {
  const sample = [
    config.projectInfo.title,
    config.projectInfo.description,
    ...config.issueboard.issues.flatMap((issue) => [
      issue.title,
      issue.description,
      issue.notes,
      issue.generated_questions,
    ]),
  ].join('\n');
  if (/[\u3040-\u30ff]/.test(sample)) return 'ja-JP';
  if (/[\uac00-\ud7af]/.test(sample)) return 'ko-KR';
  if (/[\u0600-\u06ff]/.test(sample)) return 'ar-SA';
  if (/[\u0400-\u04ff]/.test(sample)) return 'ru-RU';
  if (/[\u3400-\u9fff]/.test(sample)) return 'zh-CN';
  return 'en-US';
}

function legacyCompletionCriteria(language) {
  return language.startsWith('zh')
    ? '学习者完成该任务，并能解释自己的解决思路。'
    : 'The learner completes this task and can explain their reasoning.';
}

function legacyDebrief(language) {
  return language.startsWith('zh')
    ? '总结本任务的关键收获，并准备进入下一步。'
    : 'Summarize the key takeaways from this task and prepare for the next step.';
}
