/**
 * Hard limits applied to every inbound DSL document.
 *
 * These are *bounds*, not policies: they exist so a single request cannot make
 * the service allocate unbounded memory, recurse without end, or persist a
 * document the player can never load. Anything that exceeds a limit is rejected
 * with a named error — never silently truncated, because a truncated stage is a
 * different stage.
 */

export const DSL_LIMITS = {
  /** Serialized document size accepted from the gateway. */
  maxDocumentBytes: 2 * 1024 * 1024,
  /** Scenes per stage. */
  maxScenes: 200,
  /** Actions per scene. */
  maxActionsPerScene: 200,
  /** Whiteboard slides per scene / per stage. */
  maxWhiteboards: 100,
  /** Generated agents per stage. */
  maxAgents: 24,
  /** Nested container depth of any inbound value (objects + arrays). */
  maxDepth: 24,
  /** Length of a single sanitized string. */
  maxStringLength: 8192,
  /** Inline `html` payload of an interactive scene. */
  maxInlineHtmlBytes: 512 * 1024,
  /** Quiz questions per scene. */
  maxQuizQuestions: 100,
  /** Options per quiz question. */
  maxQuizOptions: 26,
} as const;

export type DslLimitName = keyof typeof DSL_LIMITS;

/** Thrown when a document exceeds a declared limit. */
export class DslLimitError extends Error {
  readonly limit: DslLimitName;
  readonly actual: number;

  constructor(limit: DslLimitName, actual: number, message?: string) {
    super(message ?? `dsl: ${limit} limit exceeded (${actual} > ${DSL_LIMITS[limit]})`);
    this.name = 'DslLimitError';
    this.limit = limit;
    this.actual = actual;
  }
}

/**
 * Measure the nesting depth of a value, stopping as soon as `max` is exceeded so
 * a pathological document cannot make this walk itself expensive.
 *
 * Returns the first depth at which the limit is breached, or `null` when the
 * value is within bounds.
 */
export function depthBeyond(value: unknown, max: number = DSL_LIMITS.maxDepth): number | null {
  // Iterative on purpose: a recursive implementation would blow the stack on the
  // exact input it is meant to defend against.
  const stack: Array<{ node: unknown; depth: number }> = [{ node: value, depth: 0 }];
  while (stack.length) {
    const { node, depth } = stack.pop() as { node: unknown; depth: number };
    if (depth > max) return depth;
    if (Array.isArray(node)) {
      for (const child of node) stack.push({ node: child, depth: depth + 1 });
    } else if (typeof node === 'object' && node !== null) {
      for (const child of Object.values(node)) stack.push({ node: child, depth: depth + 1 });
    }
  }
  return null;
}

/** UTF-8 byte length, matching what actually goes over the wire and onto disk. */
export function byteLength(value: string): number {
  return Buffer.byteLength(value, 'utf8');
}
