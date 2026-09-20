/**
 * Stage / Scene / Action contract constants — ported from `@openmaic/dsl` v1.0.3
 * (`packages/@openmaic/dsl/src/{stage,action,interactive}.ts`), MIT.
 *
 * Only the *closed vocabularies* and the structural shapes this service must
 * validate are ported. The upstream widget payloads are open-ended by design
 * (`WidgetConfigBase` names only `type`), so they are typed as open records here
 * too rather than being re-invented.
 */

// ==================== Scene ====================

export type SceneType = 'slide' | 'quiz' | 'interactive' | 'pbl';

export const SCENE_TYPES = ['slide', 'quiz', 'interactive', 'pbl'] as const;

export function isSceneType(value: unknown): value is SceneType {
  return typeof value === 'string' && (SCENE_TYPES as readonly string[]).includes(value);
}

export type StageMode = 'autonomous' | 'playback' | 'edit';

export const STAGE_MODES = ['autonomous', 'playback', 'edit'] as const;

export function isStageMode(value: unknown): value is StageMode {
  return typeof value === 'string' && (STAGE_MODES as readonly string[]).includes(value);
}

// ==================== Widget ====================

export type WidgetType =
  | 'simulation'
  | 'diagram'
  | 'code'
  | 'game'
  | 'visualization3d'
  | 'procedural-skill';

export const WIDGET_TYPES = [
  'simulation',
  'diagram',
  'code',
  'game',
  'visualization3d',
  'procedural-skill',
] as const;

export function isWidgetType(value: unknown): value is WidgetType {
  return typeof value === 'string' && (WIDGET_TYPES as readonly string[]).includes(value);
}

// ==================== Action ====================

export const ACTION_TYPES = [
  'spotlight',
  'laser',
  'play_video',
  'speech',
  'wb_open',
  'wb_draw_text',
  'wb_draw_shape',
  'wb_draw_chart',
  'wb_draw_latex',
  'wb_draw_table',
  'wb_draw_line',
  'wb_draw_code',
  'wb_edit_code',
  'wb_clear',
  'wb_delete',
  'wb_close',
  'discussion',
  'widget_highlight',
  'widget_setState',
  'widget_annotation',
  'widget_reveal',
] as const;

export type ActionType = (typeof ACTION_TYPES)[number];

/** Action types that fire immediately without blocking the next action. */
export const FIRE_AND_FORGET_ACTIONS: readonly ActionType[] = ['spotlight', 'laser'];

/** Action types that only work on slide scenes (they need canvas elements). */
export const SLIDE_ONLY_ACTIONS: readonly ActionType[] = ['spotlight', 'laser'];

/** Action types that must complete before the next action runs. */
export const SYNC_ACTIONS: readonly ActionType[] = [
  'speech',
  'play_video',
  'wb_open',
  'wb_draw_text',
  'wb_draw_shape',
  'wb_draw_chart',
  'wb_draw_latex',
  'wb_draw_table',
  'wb_draw_line',
  'wb_draw_code',
  'wb_edit_code',
  'wb_clear',
  'wb_delete',
  'wb_close',
  'discussion',
  'widget_highlight',
  'widget_setState',
  'widget_annotation',
  'widget_reveal',
];

export function isActionType(value: unknown): value is ActionType {
  return typeof value === 'string' && (ACTION_TYPES as readonly string[]).includes(value);
}

// ==================== Structural shapes ====================

export interface ActionBase {
  id: string;
  title?: string;
  description?: string;
}

export interface Action extends ActionBase {
  type: ActionType;
  [key: string]: unknown;
}

export interface QuizOption {
  label: string;
  value: string;
}

export interface QuizQuestion {
  id: string;
  type: 'single' | 'multiple' | 'short_answer';
  question: string;
  options?: QuizOption[];
  answer?: string[];
  analysis?: string;
  points?: number;
}

export interface SlideContent {
  type: 'slide';
  schemaVersion?: number;
  /** Readable source retained alongside the composed canvas for narration. */
  slide?: unknown;
  canvas: Record<string, unknown>;
}

export interface QuizContent {
  type: 'quiz';
  questions: QuizQuestion[];
}

export interface InteractiveContent {
  type: 'interactive';
  url?: string;
  html?: string;
  widgetType?: WidgetType;
  widgetConfig?: Record<string, unknown>;
}

export interface PblContent {
  type: 'pbl';
  [key: string]: unknown;
}

export type SceneContent = SlideContent | QuizContent | InteractiveContent | PblContent;

export interface MultiAgentConfig {
  enabled: boolean;
  agentIds: string[];
  directorPrompt?: string;
}

export interface SceneCore {
  id: string;
  stageId: string;
  title: string;
  order: number;
  actions?: Action[];
  whiteboards?: Record<string, unknown>[];
  multiAgent?: MultiAgentConfig;
  createdAt?: number;
  updatedAt?: number;
}

export type Scene = SceneCore & { type: SceneType; content: SceneContent };

export interface VoiceDesign {
  identity: string;
  texture: string;
  delivery: string;
}

export interface AgentVoiceConfig {
  providerId: string;
  modelId?: string;
  voiceId: string;
}

export interface GeneratedAgentConfig {
  id: string;
  name: string;
  role: string;
  persona: string;
  avatar: string;
  color: string;
  priority: number;
  voiceConfig?: AgentVoiceConfig;
  voiceDesign?: VoiceDesign;
}

export interface Stage {
  id: string;
  name: string;
  description?: string;
  createdAt: number;
  updatedAt: number;
  languageDirective?: string;
  style?: string;
  whiteboard?: Record<string, unknown>[];
  videoManifest?: Record<string, unknown>;
  agentIds?: string[];
  generatedAgentConfigs?: GeneratedAgentConfig[];
  interactiveMode?: boolean;
  taskEngineMode?: boolean;
}

/** The migratable aggregate: a stage row plus its ordered scene rows. */
export interface StageAggregate {
  stage: Stage;
  scenes: Scene[];
}
