/**
 * Playback planning.
 *
 * The player must never invent a scene it cannot render, so the plan this module
 * produces states, per scene, **how** it will be rendered and — when it cannot be
 * — why. Three rules:
 *
 * 1. **Degradation is explicit.** An unknown scene type, or a widget whose
 *    external dependency is missing, yields `kind: 'unsupported'` with a reason
 *    code. Nothing is faked into a native renderer, and the UI can say what is
 *    actually missing.
 * 2. **Sandboxed content stays sandboxed.** Only interactive HTML/URL content
 *    gets a `sandbox` attribute, and `allow-same-origin` is never part of it:
 *    with both `allow-scripts` and `allow-same-origin` the frame can reach the
 *    parent document, which defeats the sandbox entirely.
 * 3. **Dropped actions are reported, not silently removed.** An action that only
 *    works on a slide (spotlight/laser) is meaningless on a quiz scene; the plan
 *    lists it under `dropped_actions` so the editor can explain why a scene is
 *    quieter than authored.
 */

import {
  FIRE_AND_FORGET_ACTIONS,
  SLIDE_ONLY_ACTIONS,
  WIDGET_TYPES,
  isSceneType,
  isWidgetType,
  type Action,
  type Scene,
  type SceneType,
  type StageAggregate,
  type WidgetType,
} from '../dsl/contract.ts';

export type RenderKind = 'native' | 'sandbox-html' | 'sandbox-url' | 'unsupported';

/**
 * The only sandbox the player ever applies.
 *
 * `allow-scripts` lets the scene run its own code (that is the point of an
 * interactive scene); without `allow-same-origin` the frame gets an opaque
 * origin, so it cannot read cookies, storage or the parent DOM. Popups, forms,
 * top-level navigation, downloads and pointer-lock stay blocked by default.
 */
export const SCENE_SANDBOX = 'allow-scripts';

/** Widgets whose rendering needs a capability the deployment may not have. */
export interface RenderCapabilities {
  /** Whether an external 3D/CDN origin is configured and reachable. */
  externalCdnAvailable: boolean;
}

export interface ActionStep {
  action_id: string;
  type: string;
  /** `sync` steps must finish before the next one; `fire_and_forget` do not. */
  mode: 'sync' | 'fire_and_forget';
}

export interface DroppedAction {
  action_id: string;
  type: string;
  reason: string;
}

export interface ScenePlayback {
  id: string;
  type: SceneType | 'unknown';
  title: string;
  order: number;
  render: {
    kind: RenderKind;
    /** Only present for sandboxed content; never contains `allow-same-origin`. */
    sandbox?: string;
    widget_type?: WidgetType;
    reason?: string;
  };
  steps: ActionStep[];
  dropped_actions: DroppedAction[];
  whiteboards: number;
  multi_agent: boolean;
}

export interface PlaybackPlan {
  stage_id: string;
  workspace_id: string;
  title: string;
  revision: number;
  dsl_version: string;
  start_index: number;
  scenes: ScenePlayback[];
  degraded: Array<{ scene_id: string; reason: string }>;
}

function classifyActions(actions: readonly Action[] | undefined, sceneType: string) {
  const steps: ActionStep[] = [];
  const dropped: DroppedAction[] = [];
  const fireAndForget = new Set<string>(FIRE_AND_FORGET_ACTIONS);
  const slideOnly = new Set<string>(SLIDE_ONLY_ACTIONS);

  for (const action of actions ?? []) {
    if (slideOnly.has(action.type) && sceneType !== 'slide') {
      // Refusing to run it is correct; hiding that we refused is not.
      dropped.push({ action_id: action.id, type: action.type, reason: 'action_requires_slide_scene' });
      continue;
    }
    steps.push({
      action_id: action.id,
      type: action.type,
      mode: fireAndForget.has(action.type) ? 'fire_and_forget' : 'sync',
    });
  }
  return { steps, dropped };
}

function renderFor(scene: Scene, capabilities: RenderCapabilities): ScenePlayback['render'] {
  if (!isSceneType(scene.type)) {
    return { kind: 'unsupported', reason: 'scene_type_unsupported' };
  }
  if (scene.type !== 'interactive') return { kind: 'native' };

  const content = scene.content;
  const widgetType = content?.widgetType;
  if (widgetType !== undefined && !isWidgetType(widgetType)) {
    return { kind: 'unsupported', reason: 'widget_type_unknown' };
  }
  // `visualization3d` is the one widget family whose rendering depends on an
  // external origin; without it the scene degrades instead of rendering blank.
  if (widgetType === 'visualization3d' && !capabilities.externalCdnAvailable) {
    return { kind: 'unsupported', widget_type: widgetType, reason: 'widget_requires_external_cdn' };
  }

  if (typeof content?.html === 'string' && content.html.trim().length > 0) {
    return { kind: 'sandbox-html', sandbox: SCENE_SANDBOX, ...(widgetType ? { widget_type: widgetType } : {}) };
  }
  if (typeof content?.url === 'string' && content.url.trim().length > 0) {
    return { kind: 'sandbox-url', sandbox: SCENE_SANDBOX, ...(widgetType ? { widget_type: widgetType } : {}) };
  }
  return { kind: 'unsupported', reason: 'interactive_payload_missing' };
}

/**
 * Build the playable plan for one aggregate.
 *
 * `startIndex` is derived from `startSceneId` so a refresh can resume where the
 * student stopped; an unknown id is an explicit error rather than silently
 * restarting from scene 0.
 */
export function buildPlaybackPlan(
  document: StageAggregate,
  input: { workspaceId: string; revision: number; dslVersion: string; startSceneId?: string | null },
  capabilities: RenderCapabilities,
): PlaybackPlan {
  const scenes = [...document.scenes].sort((left, right) => left.order - right.order);
  let startIndex = 0;
  if (input.startSceneId) {
    const found = scenes.findIndex((scene) => scene.id === input.startSceneId);
    if (found === -1) throw new PlaybackError('scene_not_found', `找不到场景 ${input.startSceneId}`);
    startIndex = found;
  }

  const planned: ScenePlayback[] = scenes.map((scene) => {
    const { steps, dropped } = classifyActions(scene.actions, String(scene.type));
    return {
      id: scene.id,
      type: isSceneType(scene.type) ? scene.type : 'unknown',
      title: scene.title,
      order: scene.order,
      render: renderFor(scene, capabilities),
      steps,
      dropped_actions: dropped,
      whiteboards: Array.isArray(scene.whiteboards) ? scene.whiteboards.length : 0,
      multi_agent: Boolean(scene.multiAgent?.enabled),
    };
  });

  return {
    stage_id: document.stage.id,
    workspace_id: input.workspaceId,
    title: document.stage.name,
    revision: input.revision,
    dsl_version: input.dslVersion,
    start_index: startIndex,
    scenes: planned,
    degraded: planned
      .filter((scene) => scene.render.kind === 'unsupported')
      .map((scene) => ({ scene_id: scene.id, reason: scene.render.reason ?? 'unsupported' })),
  };
}

export class PlaybackError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(`playback: ${message}`);
    this.name = 'PlaybackError';
    this.code = code;
  }
}

export const KNOWN_WIDGET_TYPES = WIDGET_TYPES;
