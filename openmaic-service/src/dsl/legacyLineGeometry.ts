/**
 * Pure cleanup for legacy `line` elements carrying the stray `rotate` / `height`
 * fields the slide contract omits — ported from `@openmaic/dsl` v1.0.3
 * (`packages/@openmaic/dsl/src/legacy-line-geometry.ts`), MIT.
 *
 * Documents written before version stamping existed were never schema-checked, so
 * a stray `rotate` (and in principle a `height`) could survive into storage on a
 * `line` element. Stripping is lossless: line geometry is fully determined by
 * `left` / `top` / `width` plus `start` / `end`, and no reader or writer uses
 * `rotate` on a line element.
 *
 * Semantics (mirroring upstream):
 *   - never mutates its input; stripped elements are fresh objects and the
 *     enclosing objects are copied along the touched path;
 *   - returns the input **by identity** when nothing needs stripping, so callers
 *     can detect a no-op cheaply;
 *   - shares every untouched subtree by reference;
 *   - idempotent;
 *   - never throws and never invents shape — anything unexpected passes through.
 *
 * Every line-element surface of every migratable envelope is walked: a Stage
 * aggregate (`{ stage, scenes }`), a single Scene row, or a single Stage row.
 */

type Raw = Record<string, unknown>;

function isObject(value: unknown): value is Raw {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** The stray fields legacy runtimes could persist on a `line` element. */
const STRIPPED_LINE_FIELDS: readonly string[] = ['rotate', 'height'];

function ownsAnyField(element: unknown, fields: readonly string[]): element is Raw {
  return isObject(element) && fields.some((field) => Object.hasOwn(element, field));
}

/**
 * Strip the stray fields from one `elements` array. Returns `undefined` when the
 * array needs no change (so the caller can keep the original by identity).
 */
function stripElements(elements: unknown): unknown[] | undefined {
  if (!Array.isArray(elements)) return undefined;
  let next: unknown[] | undefined;
  elements.forEach((element, index) => {
    if (!isObject(element) || element.type !== 'line') return;
    if (!ownsAnyField(element, STRIPPED_LINE_FIELDS)) return;
    const cleaned: Raw = { ...element };
    for (const field of STRIPPED_LINE_FIELDS) delete cleaned[field];
    (next ??= [...elements])[index] = cleaned;
  });
  return next;
}

/** A slide surface hangs its `elements` directly off the slide object. */
function stripSlide(slide: unknown): unknown | undefined {
  if (!isObject(slide)) return undefined;
  const nextElements = stripElements(slide.elements);
  if (nextElements === undefined) return undefined;
  return { ...slide, elements: nextElements };
}

function stripSlideList(slides: unknown): unknown[] | undefined {
  if (!Array.isArray(slides)) return undefined;
  let next: unknown[] | undefined;
  slides.forEach((slide, index) => {
    const cleaned = stripSlide(slide);
    if (cleaned === undefined) return;
    (next ??= [...slides])[index] = cleaned;
  });
  return next;
}

/** `content.canvas.elements` — the primary slide canvas. */
function stripSceneFields(scene: Raw): unknown | undefined {
  let changed = false;
  const out: Raw = { ...scene };

  const content = scene.content;
  if (isObject(content) && isObject(content.canvas)) {
    const nextElements = stripElements((content.canvas as Raw).elements);
    if (nextElements !== undefined) {
      out.content = { ...content, canvas: { ...(content.canvas as Raw), elements: nextElements } };
      changed = true;
    }
  }

  const nextWhiteboards = stripSlideList(scene.whiteboards);
  if (nextWhiteboards !== undefined) {
    out.whiteboards = nextWhiteboards;
    changed = true;
  }

  return changed ? out : undefined;
}

/** `stage.whiteboard[*].elements` — stage-level explainer boards. */
function stripStageFields(stage: Raw): unknown | undefined {
  const nextWhiteboard = stripSlideList(stage.whiteboard);
  if (nextWhiteboard === undefined) return undefined;
  return { ...stage, whiteboard: nextWhiteboard };
}

export function stripLegacyLineGeometry(doc: unknown): unknown {
  if (!isObject(doc)) return doc;

  // Single Scene row: slide surfaces hang off `content.canvas` / `whiteboards`.
  const asScene = stripSceneFields(doc);
  if (asScene !== undefined) return asScene;

  // Single Stage row: explainer boards hang off `whiteboard`.
  const asStage = stripStageFields(doc);
  if (asStage !== undefined) return asStage;

  // Stage aggregate: the scenes array, plus the embedded stage row whose
  // explainer boards can carry the same stray fields.
  if (!Array.isArray(doc.scenes)) return doc;

  let nextScenes: unknown[] | undefined;
  (doc.scenes as unknown[]).forEach((scene, index) => {
    if (!isObject(scene)) return;
    const cleaned = stripSceneFields(scene);
    if (cleaned === undefined) return;
    (nextScenes ??= [...(doc.scenes as unknown[])])[index] = cleaned;
  });

  const nextStage = isObject(doc.stage) ? stripStageFields(doc.stage) : undefined;
  if (nextScenes === undefined && nextStage === undefined) return doc;
  return {
    ...doc,
    ...(nextScenes !== undefined ? { scenes: nextScenes } : {}),
    ...(nextStage !== undefined ? { stage: nextStage } : {}),
  };
}
