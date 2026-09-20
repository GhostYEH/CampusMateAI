/**
 * Stage editing commands.
 *
 * The editor never PATCHes a document wholesale: a client that sends the whole
 * aggregate back can silently revert a concurrent change it never saw, and the
 * `If-Match` revision only protects the row, not the parts of the document the
 * author did not touch. A command list says *what changed*, so the service can
 * apply it to the row it just read inside the request transaction.
 *
 * Three rules hold for every command:
 *
 * 1. **`order` stays dense and unique.** The validator rejects duplicate orders,
 *    and a UI that renders "scene 3 of 5" must not have to cope with holes, so
 *    orders are re-derived from array position after each mutation.
 * 2. **A command either applies fully or not at all.** Unknown command types,
 *    missing scenes and out-of-range targets raise {@link DslCommandError}
 *    before anything is written; the caller never persists a half-applied list.
 * 3. **Type-specific content is never invented.** `scene.create` fills in the
 *    minimal *valid* content for a shape that has one, but an `interactive`
 *    scene without `html`/`url` is refused rather than created broken.
 *
 * The result is an ordinary aggregate; the write path still runs it through
 * `prepareStage` (migrate → sanitize → validate) before it is stored.
 */

import { randomUUID } from 'node:crypto';

import {
  SCENE_TYPES,
  isSceneType,
  type Action,
  type Scene,
  type SceneContent,
  type SceneType,
  type StageAggregate,
} from './contract.ts';
import { DSL_LIMITS, DslLimitError } from './limits.ts';

export const STAGE_COMMANDS = [
  'stage.update',
  'scene.create',
  'scene.delete',
  'scene.duplicate',
  'scene.move',
  'scene.update',
  'slide.element.move',
] as const;

export type StageCommandType = (typeof STAGE_COMMANDS)[number];

const STAGE_COMMAND_SET = new Set<string>(STAGE_COMMANDS);

export function isStageCommandType(value: unknown): value is StageCommandType {
  return typeof value === 'string' && STAGE_COMMAND_SET.has(value);
}

export class DslCommandError extends Error {
  readonly code: string;
  readonly path: string;

  constructor(code: string, path: string, message: string) {
    super(`dsl command: ${message}`);
    this.name = 'DslCommandError';
    this.code = code;
    this.path = path;
  }
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function nonEmptyString(value: unknown, path: string): string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new DslCommandError('command_field_required', path, `${path} 必须是非空字符串`);
  }
  return value.trim();
}

function optionalText(value: unknown, path: string, maxLength: number): string | undefined {
  if (value === undefined) return undefined;
  if (typeof value !== 'string') {
    throw new DslCommandError('command_field_invalid', path, `${path} 必须是字符串`);
  }
  if (value.length > maxLength) {
    throw new DslCommandError('command_field_too_long', path, `${path} 超长（>${maxLength}）`);
  }
  return value;
}

/**
 * Minimal *valid* content for a scene type.
 *
 * `interactive` is deliberately absent: an interactive scene without `html` or
 * `url` fails validation, and manufacturing an empty one would put an
 * unopenable scene in front of a student. `applySceneCreate` refuses that case
 * with a path that names the offending command.
 */
function minimalContent(type: SceneType): SceneContent {
  switch (type) {
    case 'slide':
      return { type: 'slide', canvas: {} } as SceneContent;
    case 'quiz':
      return { type: 'quiz', questions: [] } as SceneContent;
    case 'pbl':
      return { type: 'pbl' } as SceneContent;
    default:
      throw new DslCommandError('interactive_content_required', 'content', '新建 interactive 场景必须提供 html 或 url');
  }
}

function newSceneId(): string {
  return `scn_${randomUUID().replaceAll('-', '')}`;
}

/** Re-derive `order` from array position so it is always dense and unique. */
function reindex(scenes: Scene[]): Scene[] {
  return scenes.map((scene, index) => (scene.order === index ? scene : { ...scene, order: index }));
}

function sceneIndexOf(scenes: readonly Scene[], sceneId: string, path: string): number {
  const index = scenes.findIndex((scene) => scene.id === sceneId);
  if (index === -1) {
    throw new DslCommandError('scene_not_found', path, `找不到场景 ${sceneId}`);
  }
  return index;
}

function requireSceneId(command: Record<string, unknown>, path: string): string {
  return nonEmptyString(command.sceneId, `${path}.sceneId`);
}

/** Insert position: immediately after `afterSceneId`, otherwise at the end. */
function insertionIndex(scenes: readonly Scene[], command: Record<string, unknown>, path: string): number {
  if (command.afterSceneId === undefined || command.afterSceneId === null) return scenes.length;
  const anchor = nonEmptyString(command.afterSceneId, `${path}.afterSceneId`);
  return sceneIndexOf(scenes, anchor, `${path}.afterSceneId`) + 1;
}

function applyStageUpdate(aggregate: StageAggregate, command: Record<string, unknown>, path: string): StageAggregate {
  const patch: Record<string, unknown> = {};
  const name = optionalText(command.name, `${path}.name`, 200);
  const description = optionalText(command.description, `${path}.description`, 4000);
  const style = optionalText(command.style, `${path}.style`, 200);
  if (name !== undefined) patch.name = name;
  if (description !== undefined) patch.description = description;
  if (style !== undefined) patch.style = style;
  for (const flag of ['interactiveMode', 'taskEngineMode'] as const) {
    if (command[flag] === undefined) continue;
    if (typeof command[flag] !== 'boolean') {
      throw new DslCommandError('command_field_invalid', `${path}.${flag}`, `${flag} 必须是布尔值`);
    }
    patch[flag] = command[flag];
  }
  if (Object.keys(patch).length === 0) {
    throw new DslCommandError('command_no_effect', path, 'stage.update 没有提供任何可更新字段');
  }
  return { ...aggregate, stage: { ...aggregate.stage, ...patch } };
}

function applySceneCreate(
  aggregate: StageAggregate,
  command: Record<string, unknown>,
  path: string,
  now: number,
): StageAggregate {
  if (!isSceneType(command.sceneType)) {
    throw new DslCommandError(
      'scene_type_invalid',
      `${path}.sceneType`,
      `sceneType 必须是 ${SCENE_TYPES.join('/')}`,
    );
  }
  const title = optionalText(command.title, `${path}.title`, 200) ?? '新场景';
  if (command.sceneType === 'interactive' && command.content === undefined) {
    // Refused with the command's own path so the editor can point at the row the
    // author has to fix rather than at the document in general.
    throw new DslCommandError(
      'interactive_content_required',
      `${path}.content`,
      '新建 interactive 场景必须提供 html 或 url',
    );
  }
  let content: SceneContent;
  if (command.content === undefined) {
    content = minimalContent(command.sceneType);
  } else {
    if (!isObject(command.content)) {
      throw new DslCommandError('command_field_invalid', `${path}.content`, 'content 必须是对象');
    }
    if (command.content.type !== command.sceneType) {
      throw new DslCommandError(
        'content_type_mismatch',
        `${path}.content.type`,
        'content.type 必须与 sceneType 一致',
      );
    }
    content = command.content as SceneContent;
  }

  const scenes = aggregate.scenes.slice();
  const at = insertionIndex(scenes, command, path);
  const scene: Scene = {
    id: newSceneId(),
    stageId: aggregate.stage.id,
    title,
    order: at,
    type: command.sceneType,
    content,
    createdAt: now,
    updatedAt: now,
  };
  if (Array.isArray(command.actions)) scene.actions = command.actions as Action[];
  scenes.splice(at, 0, scene);
  return { ...aggregate, scenes: reindex(scenes) };
}

function applySceneDelete(
  aggregate: StageAggregate,
  command: Record<string, unknown>,
  path: string,
): StageAggregate {
  const sceneId = requireSceneId(command, path);
  const index = sceneIndexOf(aggregate.scenes, sceneId, `${path}.sceneId`);
  const scenes = aggregate.scenes.slice();
  scenes.splice(index, 1);
  return { ...aggregate, scenes: reindex(scenes) };
}

function applySceneDuplicate(
  aggregate: StageAggregate,
  command: Record<string, unknown>,
  path: string,
  now: number,
): StageAggregate {
  const sceneId = requireSceneId(command, path);
  const index = sceneIndexOf(aggregate.scenes, sceneId, `${path}.sceneId`);
  const source = aggregate.scenes[index];
  const title = optionalText(command.title, `${path}.title`, 200) ?? `${source.title}（副本）`;
  const scenes = aggregate.scenes.slice();
  scenes.splice(index + 1, 0, {
    ...source,
    // Deep-copy the mutable payloads so editing the copy cannot reach back into
    // the original scene object that is still in the document.
    content: structuredClone(source.content),
    ...(source.actions ? { actions: structuredClone(source.actions) } : {}),
    ...(source.whiteboards ? { whiteboards: structuredClone(source.whiteboards) } : {}),
    id: newSceneId(),
    title,
    order: index + 1,
    createdAt: now,
    updatedAt: now,
  });
  return { ...aggregate, scenes: reindex(scenes) };
}

function applySceneMove(
  aggregate: StageAggregate,
  command: Record<string, unknown>,
  path: string,
): StageAggregate {
  const sceneId = requireSceneId(command, path);
  const from = sceneIndexOf(aggregate.scenes, sceneId, `${path}.sceneId`);
  const to = command.toIndex;
  if (typeof to !== 'number' || !Number.isInteger(to) || to < 0 || to >= aggregate.scenes.length) {
    throw new DslCommandError(
      'scene_move_out_of_range',
      `${path}.toIndex`,
      `toIndex 必须在 0..${aggregate.scenes.length - 1} 之间`,
    );
  }
  const scenes = aggregate.scenes.slice();
  const [moved] = scenes.splice(from, 1);
  scenes.splice(to, 0, moved);
  return { ...aggregate, scenes: reindex(scenes) };
}

function applySceneUpdate(
  aggregate: StageAggregate,
  command: Record<string, unknown>,
  path: string,
  now: number,
): StageAggregate {
  const sceneId = requireSceneId(command, path);
  const index = sceneIndexOf(aggregate.scenes, sceneId, `${path}.sceneId`);
  const patch: Partial<Scene> = { updatedAt: now };

  const title = optionalText(command.title, `${path}.title`, 200);
  if (title !== undefined) patch.title = title;

  if (command.content !== undefined) {
    if (!isObject(command.content)) {
      throw new DslCommandError('command_field_invalid', `${path}.content`, 'content 必须是对象');
    }
    if (command.content.type !== aggregate.scenes[index].type) {
      throw new DslCommandError(
        'content_type_mismatch',
        `${path}.content.type`,
        '不能通过 update 改变场景类型；请新建一个场景',
      );
    }
    patch.content = command.content as SceneContent;
  }

  if (command.actions !== undefined) {
    if (!Array.isArray(command.actions)) {
      throw new DslCommandError('command_field_invalid', `${path}.actions`, 'actions 必须是数组');
    }
    patch.actions = command.actions as Action[];
  }

  if (command.whiteboards !== undefined) {
    if (!Array.isArray(command.whiteboards)) {
      throw new DslCommandError('command_field_invalid', `${path}.whiteboards`, 'whiteboards 必须是数组');
    }
    patch.whiteboards = command.whiteboards;
  }

  if (command.multiAgent !== undefined) {
    if (!isObject(command.multiAgent)) {
      throw new DslCommandError('command_field_invalid', `${path}.multiAgent`, 'multiAgent 必须是对象');
    }
    patch.multiAgent = command.multiAgent as Scene['multiAgent'];
  }

  if (Object.keys(patch).length === 1) {
    throw new DslCommandError('command_no_effect', path, 'scene.update 没有提供任何可更新字段');
  }

  const scenes = aggregate.scenes.slice();
  scenes[index] = { ...scenes[index], ...patch };
  return { ...aggregate, scenes };
}

function finiteCoordinate(command: Record<string, unknown>, path: string, field: 'left' | 'top'): number {
  const value = command[field];
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new DslCommandError('command_field_invalid', `${path}.${field}`, `${path}.${field} 必须是有限数字`);
  }
  return value;
}

/** Move one existing slide element without touching its payload or action timeline. */
function applySlideElementMove(
  aggregate: StageAggregate,
  command: Record<string, unknown>,
  path: string,
): StageAggregate {
  const sceneId = requireSceneId(command, path);
  const elementId = nonEmptyString(command.elementId, `${path}.elementId`);
  const left = finiteCoordinate(command, path, 'left');
  const top = finiteCoordinate(command, path, 'top');
  const sceneIndex = sceneIndexOf(aggregate.scenes, sceneId, `${path}.sceneId`);
  const scene = aggregate.scenes[sceneIndex];
  if (scene.type !== 'slide' || scene.content.type !== 'slide') {
    throw new DslCommandError(
      'slide_element_requires_slide',
      `${path}.sceneId`,
      'slide.element.move 只能作用于 slide 场景',
    );
  }
  const canvas = scene.content.canvas;
  const elements = isObject(canvas) && Array.isArray(canvas.elements) ? canvas.elements : [];
  const elementIndex = elements.findIndex(
    (element) => isObject(element) && element.id === elementId,
  );
  if (elementIndex === -1) {
    throw new DslCommandError('element_not_found', `${path}.elementId`, `找不到元素 ${elementId}`);
  }
  const target = elements[elementIndex] as Record<string, unknown>;
  if (
    typeof target.left !== 'number' || !Number.isFinite(target.left) ||
    typeof target.top !== 'number' || !Number.isFinite(target.top)
  ) {
    throw new DslCommandError(
      'element_position_invalid',
      `${path}.elementId`,
      `元素 ${elementId} 缺少有限的 left/top 坐标`,
    );
  }
  const nextElements = elements.slice();
  nextElements[elementIndex] = { ...target, left, top };
  const nextScene = {
    ...scene,
    content: { ...scene.content, canvas: { ...canvas, elements: nextElements } },
  };
  const scenes = aggregate.scenes.slice();
  scenes[sceneIndex] = nextScene;
  return { ...aggregate, scenes };
}

export interface ApplyOptions {
  /** Injected for deterministic fixture output; defaults to `Date.now()`. */
  now?: number;
}

/**
 * Apply an ordered command list to one aggregate.
 *
 * Nothing is written here: the returned aggregate is handed to the stage write
 * path, which re-runs the DSL ladder. A command list that exceeds
 * {@link DSL_LIMITS.maxCommandsPerRequest} is a named limit violation rather than
 * an arbitrarily long request.
 */
export function applyStageCommands(
  document: StageAggregate,
  commands: readonly unknown[],
  options: ApplyOptions = {},
): StageAggregate {
  if (!Array.isArray(commands) || commands.length === 0) {
    throw new DslCommandError('commands_empty', 'commands', '至少需要一条命令');
  }
  if (commands.length > DSL_LIMITS.maxCommandsPerRequest) {
    throw new DslLimitError('maxCommandsPerRequest', commands.length);
  }

  const now = options.now ?? Date.now();
  let aggregate = document;

  commands.forEach((rawCommand, index) => {
    const path = `commands[${index}]`;
    if (!isObject(rawCommand)) {
      throw new DslCommandError('command_not_object', path, '命令必须是对象');
    }
    if (!isStageCommandType(rawCommand.type)) {
      throw new DslCommandError(
        'command_type_invalid',
        `${path}.type`,
        `命令类型必须是 ${STAGE_COMMANDS.join('/')}`,
      );
    }
    if (aggregate.scenes.length > DSL_LIMITS.maxScenes) {
      throw new DslLimitError('maxScenes', aggregate.scenes.length);
    }

    switch (rawCommand.type) {
      case 'stage.update':
        aggregate = applyStageUpdate(aggregate, rawCommand, path);
        break;
      case 'scene.create':
        aggregate = applySceneCreate(aggregate, rawCommand, path, now);
        break;
      case 'scene.delete':
        aggregate = applySceneDelete(aggregate, rawCommand, path);
        break;
      case 'scene.duplicate':
        aggregate = applySceneDuplicate(aggregate, rawCommand, path, now);
        break;
      case 'scene.move':
        aggregate = applySceneMove(aggregate, rawCommand, path);
        break;
      case 'scene.update':
        aggregate = applySceneUpdate(aggregate, rawCommand, path, now);
        break;
      case 'slide.element.move':
        aggregate = applySlideElementMove(aggregate, rawCommand, path);
        break;
      default: {
        const exhaustive: never = rawCommand.type;
        throw new DslCommandError('command_type_invalid', `${path}.type`, `未实现的命令 ${String(exhaustive)}`);
      }
    }
  });

  if (aggregate.scenes.length > DSL_LIMITS.maxScenes) {
    throw new DslLimitError('maxScenes', aggregate.scenes.length);
  }
  return aggregate;
}
