/**
 * Validation for the Stage aggregate.
 *
 * `validateStage` answers "is this a document we can serve"; it never repairs.
 * `prepareStage` is the single entry point a write path uses: it runs the
 * migration ladder, then sanitizes, then validates — in that order, because a
 * legacy document is only *shaped* correctly after migration, and validating
 * before sanitizing would accept text we then silently rewrite.
 *
 * Issues carry a stable `code` and a JSON path, so a client can point at the
 * offending field without the service echoing the document back.
 */

import {
  ACTION_TYPES,
  SCENE_TYPES,
  WIDGET_TYPES,
  isActionType,
  isSceneType,
  isStageMode,
  isWidgetType,
  type Action,
  type Scene,
  type Stage,
  type StageAggregate,
  type StageMode,
} from './contract.ts';
import { DSL_LIMITS, DslLimitError, byteLength, depthBeyond } from './limits.ts';
import { sanitizeInteractiveHtml, sanitizeStrings, sanitizeUrl } from './sanitize.ts';
import { DSL_VERSION, migrate } from './version.ts';

export interface ValidationIssue {
  code: string;
  path: string;
  message: string;
}

export interface ValidationResult {
  ok: boolean;
  issues: ValidationIssue[];
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function issue(code: string, path: string, message: string): ValidationIssue {
  return { code, path, message };
}

/** Validate one scene row, appending issues under `scenes[i]`. */
function validateScene(scene: unknown, index: number, stageId: string, issues: ValidationIssue[]): void {
  const path = `scenes[${index}]`;
  if (!isObject(scene)) {
    issues.push(issue('scene_not_object', path, '场景必须是对象'));
    return;
  }

  if (!isNonEmptyString(scene.id)) issues.push(issue('scene_id_missing', `${path}.id`, '场景缺少 id'));
  if (scene.stageId !== stageId) {
    issues.push(issue('scene_stage_mismatch', `${path}.stageId`, '场景的 stageId 与所属 stage 不一致'));
  }
  if (!isNonEmptyString(scene.title)) issues.push(issue('scene_title_missing', `${path}.title`, '场景缺少标题'));
  if (!isFiniteNumber(scene.order)) issues.push(issue('scene_order_invalid', `${path}.order`, '场景缺少有效的 order'));

  if (!isSceneType(scene.type)) {
    issues.push(issue('scene_type_invalid', `${path}.type`, `场景类型必须是 ${SCENE_TYPES.join('/')}`));
    return;
  }
  validateSceneContent(scene, index, issues);
  validateActions(scene.actions, index, issues);

  if (scene.whiteboards !== undefined) {
    if (!Array.isArray(scene.whiteboards)) {
      issues.push(issue('whiteboards_not_array', `${path}.whiteboards`, 'whiteboards 必须是数组'));
    } else if (scene.whiteboards.length > DSL_LIMITS.maxWhiteboards) {
      issues.push(issue('whiteboards_too_many', `${path}.whiteboards`, '白板数量超出上限'));
    }
  }
}

/**
 * The scene `type` is bound to its `content` discriminant. Consumers branch on
 * `scene.type` and then read `content` as the matching shape, so the two
 * disagreeing is a real defect rather than a stylistic one.
 */
function validateSceneContent(scene: Record<string, unknown>, index: number, issues: ValidationIssue[]): void {
  const path = `scenes[${index}].content`;
  const content = scene.content;
  if (!isObject(content)) {
    issues.push(issue('content_not_object', path, '场景缺少 content'));
    return;
  }
  if (content.type !== scene.type) {
    issues.push(issue('content_type_mismatch', `${path}.type`, 'content.type 必须与 scene.type 一致'));
    return;
  }

  if (scene.type === 'slide') {
    if (!isObject(content.canvas)) {
      issues.push(issue('slide_canvas_missing', `${path}.canvas`, 'slide 场景缺少 canvas'));
    }
    return;
  }

  if (scene.type === 'quiz') {
    const questions = content.questions;
    if (!Array.isArray(questions)) {
      issues.push(issue('quiz_questions_missing', `${path}.questions`, 'quiz 场景缺少 questions 数组'));
      return;
    }
    if (questions.length > DSL_LIMITS.maxQuizQuestions) {
      issues.push(issue('quiz_questions_too_many', `${path}.questions`, '题目数量超出上限'));
    }
    questions.forEach((question, qIndex) => {
      const qPath = `${path}.questions[${qIndex}]`;
      if (!isObject(question)) {
        issues.push(issue('quiz_question_not_object', qPath, '题目必须是对象'));
        return;
      }
      if (!isNonEmptyString(question.id)) issues.push(issue('quiz_question_id_missing', `${qPath}.id`, '题目缺少 id'));
      if (!['single', 'multiple', 'short_answer'].includes(String(question.type))) {
        issues.push(issue('quiz_question_type_invalid', `${qPath}.type`, '题目类型无效'));
      }
      if (typeof question.question !== 'string') {
        issues.push(issue('quiz_question_text_missing', `${qPath}.question`, '题目缺少题干'));
      }
      if (Array.isArray(question.options) && question.options.length > DSL_LIMITS.maxQuizOptions) {
        issues.push(issue('quiz_options_too_many', `${qPath}.options`, '选项数量超出上限'));
      }
    });
    return;
  }

  if (scene.type === 'interactive') {
    const hasHtml = typeof content.html === 'string';
    const hasUrl = typeof content.url === 'string' && content.url.trim().length > 0;
    if (!hasHtml && !hasUrl) {
      issues.push(issue('interactive_payload_missing', path, 'interactive 场景必须至少提供 html 或 url'));
    }
    if (hasUrl && sanitizeUrl(content.url as string) === null) {
      issues.push(issue('interactive_url_rejected', `${path}.url`, 'interactive url 必须是 http(s) 且不含凭据'));
    }
    if (content.widgetType !== undefined && !isWidgetType(content.widgetType)) {
      issues.push(issue('widget_type_invalid', `${path}.widgetType`, `widget 类型必须是 ${WIDGET_TYPES.join('/')}`));
    }
    if (content.widgetConfig !== undefined) {
      if (!isObject(content.widgetConfig)) {
        issues.push(issue('widget_config_not_object', `${path}.widgetConfig`, 'widgetConfig 必须是对象'));
      } else if (!isWidgetType((content.widgetConfig as Record<string, unknown>).type)) {
        issues.push(issue('widget_config_type_invalid', `${path}.widgetConfig.type`, 'widgetConfig.type 无效'));
      }
    }
    return;
  }

  // pbl: the upstream contract leaves the payload app-defined, so there is
  // nothing closed to check beyond the discriminant already matched above.
}

function validateActions(actions: unknown, sceneIndex: number, issues: ValidationIssue[]): void {
  const path = `scenes[${sceneIndex}].actions`;
  if (actions === undefined) return;
  if (!Array.isArray(actions)) {
    issues.push(issue('actions_not_array', path, 'actions 必须是数组'));
    return;
  }
  if (actions.length > DSL_LIMITS.maxActionsPerScene) {
    issues.push(issue('actions_too_many', path, '动作数量超出上限'));
    return;
  }
  actions.forEach((action, index) => {
    const actionPath = `${path}[${index}]`;
    if (!isObject(action)) {
      issues.push(issue('action_not_object', actionPath, '动作必须是对象'));
      return;
    }
    if (!isNonEmptyString(action.id)) issues.push(issue('action_id_missing', `${actionPath}.id`, '动作缺少 id'));
    if (!isActionType(action.type)) {
      issues.push(issue('action_type_invalid', `${actionPath}.type`, `动作类型必须是 ${ACTION_TYPES.join('/')}`));
      return;
    }
    if (action.type === 'speech' && typeof action.text !== 'string') {
      issues.push(issue('speech_text_missing', `${actionPath}.text`, 'speech 动作缺少 text'));
    }
  });
}

function validateStageRow(stage: unknown, issues: ValidationIssue[]): void {
  if (!isObject(stage)) {
    issues.push(issue('stage_not_object', 'stage', 'stage 必须是对象'));
    return;
  }
  if (!isNonEmptyString(stage.id)) issues.push(issue('stage_id_missing', 'stage.id', 'stage 缺少 id'));
  if (!isNonEmptyString(stage.name)) issues.push(issue('stage_name_missing', 'stage.name', 'stage 缺少 name'));
  if (!isFiniteNumber(stage.createdAt)) issues.push(issue('stage_created_at_invalid', 'stage.createdAt', 'createdAt 必须是数字'));
  if (!isFiniteNumber(stage.updatedAt)) issues.push(issue('stage_updated_at_invalid', 'stage.updatedAt', 'updatedAt 必须是数字'));
  if (stage.mode !== undefined && !isStageMode(stage.mode)) {
    issues.push(issue('stage_mode_invalid', 'stage.mode', 'stage.mode 必须是 autonomous/playback/edit'));
  }
  if (stage.agentIds !== undefined) {
    if (!Array.isArray(stage.agentIds)) {
      issues.push(issue('stage_agent_ids_not_array', 'stage.agentIds', 'agentIds 必须是数组'));
    } else if (stage.agentIds.length > DSL_LIMITS.maxAgents) {
      issues.push(issue('stage_agents_too_many', 'stage.agentIds', '智能体数量超出上限'));
    }
  }
  if (stage.generatedAgentConfigs !== undefined) {
    if (!Array.isArray(stage.generatedAgentConfigs)) {
      issues.push(issue('stage_agent_configs_not_array', 'stage.generatedAgentConfigs', 'generatedAgentConfigs 必须是数组'));
    } else if (stage.generatedAgentConfigs.length > DSL_LIMITS.maxAgents) {
      issues.push(issue('stage_agent_configs_too_many', 'stage.generatedAgentConfigs', '智能体数量超出上限'));
    }
  }
}

/** Validate an already-migrated, already-sanitized aggregate. Pure. */
export function validateStage(document: unknown): ValidationResult {
  const issues: ValidationIssue[] = [];
  if (!isObject(document)) {
    return { ok: false, issues: [issue('document_not_object', '', '文档必须是对象')] };
  }

  const depth = depthBeyond(document);
  if (depth !== null) {
    issues.push(issue('document_too_deep', '', `嵌套深度超出上限（${depth}）`));
    return { ok: false, issues };
  }

  validateStageRow(document.stage, issues);

  const scenes = document.scenes;
  if (!Array.isArray(scenes)) {
    issues.push(issue('scenes_not_array', 'scenes', 'scenes 必须是数组'));
    return { ok: false, issues };
  }
  if (scenes.length > DSL_LIMITS.maxScenes) {
    issues.push(issue('scenes_too_many', 'scenes', `场景数量超出上限（${scenes.length}）`));
    return { ok: false, issues };
  }

  const stageId = isObject(document.stage) ? String(document.stage.id ?? '') : '';
  scenes.forEach((scene, index) => validateScene(scene, index, stageId, issues));

  const orders = scenes
    .filter(isObject)
    .map((scene) => scene.order)
    .filter(isFiniteNumber);
  if (new Set(orders).size !== orders.length) {
    issues.push(issue('scene_order_duplicate', 'scenes', '同一 stage 内的 order 必须唯一'));
  }

  return { ok: issues.length === 0, issues };
}

export class DslValidationError extends Error {
  readonly issues: ValidationIssue[];

  constructor(issues: ValidationIssue[]) {
    super(`dsl: 文档校验失败（${issues.length} 项）: ${issues.map((item) => `${item.path} ${item.code}`).join(', ')}`);
    this.name = 'DslValidationError';
    this.issues = issues;
  }
}

export interface PreparedStage {
  document: StageAggregate & { dslVersion: string };
  migrated: boolean;
}

/**
 * The single write-path entry point: migrate → bound → sanitize → validate.
 *
 * Throws {@link DslLimitError} / {@link DslValidationError} rather than returning
 * a partially accepted document, so a caller can never persist something the
 * player will later refuse.
 */
export function prepareStage(raw: unknown): PreparedStage {
  const size = byteLength(typeof raw === 'string' ? raw : JSON.stringify(raw ?? null));
  if (size > DSL_LIMITS.maxDocumentBytes) {
    throw new DslLimitError('maxDocumentBytes', size);
  }

  const migratedDocument = migrate(raw);
  const migrated = migratedDocument !== raw;
  // Bound the inline HTML *before* sanitizing: an oversize payload is a named
  // limit violation, not something to silently trim and then persist.
  assertInlineHtmlWithinLimits(migratedDocument);
  const sanitized = sanitizeDocument(migratedDocument);

  const result = validateStage(sanitized);
  if (!result.ok) throw new DslValidationError(result.issues);

  const document = sanitized as StageAggregate & { dslVersion: string };
  if (document.dslVersion !== DSL_VERSION) {
    // migrate() guarantees this; asserting it keeps a future ladder edit from
    // silently writing an unstamped document.
    throw new DslValidationError([
      issue('dsl_version_unstamped', 'dslVersion', `迁移后版本不是 ${DSL_VERSION}`),
    ]);
  }
  return { document, migrated };
}

function assertInlineHtmlWithinLimits(document: unknown): void {
  if (!isObject(document) || !Array.isArray(document.scenes)) return;
  for (const scene of document.scenes) {
    if (!isObject(scene)) continue;
    const content = scene.content;
    if (!isObject(content) || content.type !== 'interactive') continue;
    if (typeof content.html !== 'string') continue;
    const bytes = byteLength(content.html);
    if (bytes > DSL_LIMITS.maxInlineHtmlBytes) {
      throw new DslLimitError('maxInlineHtmlBytes', bytes);
    }
  }
}

/** Sanitize the document's free text, plus the inline HTML surface. */
function sanitizeDocument(document: unknown): unknown {
  if (!isObject(document)) return document;
  const out = sanitizeStrings(document) as Record<string, unknown>;

  if (!Array.isArray(out.scenes)) return out;
  const scenes = (out.scenes as unknown[]).map((scene) => {
    if (!isObject(scene)) return scene;
    const content = scene.content;
    if (!isObject(content) || content.type !== 'interactive') return scene;
    if (typeof content.html !== 'string') return scene;
    const html = sanitizeInteractiveHtml(content.html);
    if (html === null) return scene; // unreachable: bounded before sanitizing
    return { ...scene, content: { ...content, html } };
  });

  return { ...out, scenes };
}

export type { Action, Scene, Stage, StageMode };
