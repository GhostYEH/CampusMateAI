/**
 * The DSL surface this service exposes to the rest of the runtime.
 *
 * Ported from `@openmaic/dsl` v1.0.3 (MIT) — see `docs/openmaic-capability-matrix.md`
 * for the exact rows and the evidence behind them. The port is a documented
 * subset: the closed vocabularies, the version/migration mechanism with its
 * cross-line guard, the legacy line-geometry transform, and the write-path
 * (bound → migrate → sanitize → validate). Upstream widget payloads stay
 * open-ended by design and are therefore not re-invented here.
 */

export {
  ACTION_TYPES,
  FIRE_AND_FORGET_ACTIONS,
  SCENE_TYPES,
  SLIDE_ONLY_ACTIONS,
  STAGE_MODES,
  SYNC_ACTIONS,
  WIDGET_TYPES,
  isActionType,
  isSceneType,
  isStageMode,
  isWidgetType,
} from './contract.ts';
export type {
  Action,
  ActionType,
  InteractiveContent,
  MultiAgentConfig,
  QuizContent,
  QuizQuestion,
  Scene,
  SceneContent,
  SceneType,
  Stage,
  StageAggregate,
  StageMode,
  WidgetType,
} from './contract.ts';

export {
  DSL_LIMITS,
  DslLimitError,
  byteLength,
  depthBeyond,
} from './limits.ts';
export type { DslLimitName } from './limits.ts';

export {
  STAGE_COMMANDS,
  DslCommandError,
  applyStageCommands,
  isStageCommandType,
} from './commands.ts';
export type { ApplyOptions, StageCommandType } from './commands.ts';

export {
  sanitizeInteractiveHtml,
  sanitizeStrings,
  sanitizeText,
  sanitizeUrl,
} from './sanitize.ts';

export {
  DslValidationError,
  prepareStage,
  validateStage,
} from './validate.ts';
export type { PreparedStage, ValidationIssue, ValidationResult } from './validate.ts';

export {
  DSL_MIGRATIONS,
  DSL_VERSION,
  DSL_VERSION_KEY,
  INITIAL_DSL_VERSION,
  RUNTIME_DSL_MIGRATIONS,
  RUNTIME_DSL_VERSION,
  RUNTIME_DSL_VERSION_KEY,
  UNVERSIONED_DSL_VERSION,
  DslVersionError,
  compareVersions,
  documentDslVersionOf,
  migrate,
  migrateRuntime,
  needsMigration,
  needsRuntimeMigration,
  stampRuntimeVersion,
  versionOf,
} from './version.ts';
export type { DslMigration, DslVersioned, RuntimeVersioned } from './version.ts';
